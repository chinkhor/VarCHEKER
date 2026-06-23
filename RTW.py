from itertools import combinations
from z3 import *
import pandas as pd
import os

class RTW_Entry:    
    def __init__(self):
        # requirement ID, for traceability
        self.ID = ""
        # indicator whether the entry is valid, 0: invalid, 1: valid
        self.Valid = 0
        # rules for parent-child relationship, including cross-tree constraint (between features of different parents) 
        # R1: root
        # R2: mandatory child
        # R3: optional child
        # R4: alternative child, select only one
        # R5: either child, select at least one
        # R6: combinations of R2 and R3
        # R7, R8, R9, R10: cross-tree constraint, only use for features of different parents
        self.Rule = ""
        # parent feature, for R7, R8, R9, R10 it represents first feature
        self.Parent = ""
        # children features, for R7, R8, R9, R10, it/they represents second feature or subsequent features
        self.Children = []
        
    def printEntry(self):
        print("ID : {}, Valid : {}, Rule : {}, Parent : {}, Children : {}".format(self.ID, self.Valid, self.Rule, self.Parent, self.Children))
        print()
        
# RTW node is a feature (unit of functionality) 
class RTW_Node:
    def __init__(self, name):
        self.parent = None
        self.children = []
        # abstract feature, does not exist in the implementation, use to group concrete features
        self.abstract = False
        self.name = name
        self.rule = ""
        # private use variable
        # use to indicate the original rule (either R2 or R3) between parent and single child before combining become R6
        self.private = ""
        self.valid = 0
        # trace the requirements (IDs) associated with the feature
        self.tracedReq = []
        # assignment for the feature: True or False
        self.assignment = ""
        
    # the feature is a terminal node, no child
    def isLeaf(self):
        if len(self.children) > 0:
            return False
        else:
            return True
        
    def printNode(self):
        print("Node: {}, valid {}, Abstract: {}, Rule: {}, private: {}".format(self.name, self.valid, self.abstract, self.rule, self.private))
        if self.parent != None:
            print("   Parent: {}".format(self.parent.name))
        else:
            print("   Parent: None")
        if len(self.children) > 0:
            for child in self.children:
                print("   Child: {}".format(child.name))
        else:
            print("   Children: None")
        print("   Requirements Traceability: {}".format(self.tracedReq))
            
class RTW:
    def __init__(self, filename):
        self.root = None
        self.solutions = []
        self.FM_XML = []
        self.constraints = {}
        self.sat_formula = []
        self.features = {}
        self.table = {}
        self.dict_result = {}
        self.dict_formula = {'R2': self.R2Formula, 'R3': self.R3Formula, 'R4': self.R4Formula, 'R5': self.R5Formula}
        self.operator_map = [
            '==', 
            '!=', 
            '>', 
            '<', 
            '>=', 
            '<='
        ]
        self.feature_assignment_choice = {}

        # sequence of method calls, the order is crucial to ensure dependencies
        # build RTW table (1st thing to do)
        if self.parseRTW(filename) == False:
            print("RTW instantiation is aborted.")
            return

        # construct RTW features/nodes (2nd thing to do) - depend on RTW table
        self.constructRTWFeatures()        
        # construct feature diagram in tree - need RTW table and RTW nodes
        self.constructRTWTree()
        # construct feature model constraints - need RTW table
        # but need to reconstruct when RTW table is changed (e.g. entry validity is changed)
        self.constructRTWConstraints()

        # analyze feature model tree - need RTW nodes and RTW tree
        self.analyzeRTWTree()
        # construct feature model sentences (propositional logic expression)
        # need RTW nodes, RTW tree and RTW constraints
        self.constructFMSentences()
        # construct feature model in XML form - need RTW table, RTW nodes, RTW tree, RTW constraints 
        self.constructXMLFeatureModel()
        # export feature model to XML file - need feature model in XML form (represented by self.FM_XML)
        self.exportFeatureModel2XML("FeatureModel.xml")
        self.support_features = self.get_support_features()
        
    # construct a single RTW entry
    def constructRTWEntry(self, record):
        entry = RTW_Entry()
        entry.ID = record["Requirement ID"].strip()
        entry.Valid = int(record["Valid"])
        entry.Rule = record["Rule"].strip()
        entry.Parent = record["Parent Feature"].strip()
        entry.Children = record["Children Features"].split(',')
        for i, child in enumerate(entry.Children):
            entry.Children[i] = entry.Children[i].strip()
        if entry.Valid == 1:
            if entry.ID not in self.table:
                self.table[entry.ID] = entry
            else:
                raise Exception(f"Duplicate ID: {entry.ID} is detected")
    
    # parse the input RTW file to extract and construct RTW entries
    def parseRTW(self, files):
        for file in files:
            try:
                df = pd.read_csv(file)
            except:
                print(f"Error reading {file}")
                return False
            records = df.to_dict("records")
            for record in records:
                self.constructRTWEntry(record)
        return True      
            
    # extract cross-tree constraints from RTW table, maintain in "self.constraints" dictionary
    # key of dictionary: requirement ID 
    # value of dictionary: propositional logic formula
    def constructRTWConstraints(self):
        self.constraints = {}
        for ID in self.table:
            entry = self.table[ID]
            if not entry.Valid:
                continue
            if entry.Rule == 'R7':
                self.constraints[ID] = entry.Parent + " => " + entry.Children[0]
            elif entry.Rule == 'R8':
                self.constraints[ID] = entry.Parent + " => !" + entry.Children[0]
            elif entry.Rule == 'R9':
                children_logic = "(" 
                for child in entry.Children:
                    children_logic = children_logic + child + " || "
                children_logic = children_logic[:-4] +")"
                self.constraints[ID] = entry.Parent + " => " + children_logic
            elif entry.Rule == 'R10':
                # to-do: support multiple children
                children_logic = "(" + entry.Children[0] + " && !" + entry.Children[1] + ")"
                children_logic = children_logic + " || (!" + entry.Children[0] + " && " + entry.Children[1] + ")"
                self.constraints[ID] = entry.Parent + " => " + children_logic

    # extract cross-tree constraints from RTW table and add them to "self.sat_formula" list (in comply with z3)
    def constructSATConstraints(self):
        for ID in self.table:
            entry = self.table[ID]
            if not entry.Valid:
                continue
            if entry.Rule == 'R7':
                parent_var = self.get_Z3_variable(entry.Parent)
                child_var = self.get_Z3_variable(entry.Children[0])
                self.sat_formula.append([Implies(parent_var, child_var), [ID]])
            elif entry.Rule == 'R8':
                parent_var = self.get_Z3_variable(entry.Parent)
                child_var = self.get_Z3_variable(entry.Children[0])
                self.sat_formula.append([Implies(parent_var, Not(child_var)), [ID]])
            elif entry.Rule == 'R9':
                children_logic = [] 
                for child in entry.Children:
                    child_var = self.get_Z3_variable(child)
                    children_logic.append(child_var)
                children_logic = Or(children_logic)
                parent_var = self.get_Z3_variable(entry.Parent)
                self.sat_formula.append([Implies(parent_var, children_logic), [ID]])
            elif entry.Rule == 'R10':
                # to-do: support multiple children
                child1_var = self.get_Z3_variable(entry.Children[0])
                child2_var = self.get_Z3_variable(entry.Children[1])
                children_logic1 = And(child1_var, Not(child2_var))
                children_logic2 = And(Not(child1_var), child2_var)
                children_logic = Or(children_logic1, children_logic2)
                parent_var = self.get_Z3_variable(entry.Parent)
                self.sat_formula.append([Implies(parent_var, children_logic), [ID]])
   
    # extract features from RTW table, maintain in "self.features" dictionary
    # key of dictionary: feature (name)
    # valud of dictionary: RTW node (object) corresponding to the feature
    def constructRTWFeatures(self):
        self.features = {}
        for ID in self.table:
            entry = self.table[ID]
            if (not entry.Valid) or (entry.Parent == 'root'):
                continue
            parent = entry.Parent.strip()
            if parent not in self.features:
                #print(f"parent feature: {parent}")
                self.features[parent] = RTW_Node(parent)
                if 'abstract_' in parent:
                    self.features[parent].abstract = True    
            # add requirement ID to the node's requirement tracing list (variable tracedReq)
            if entry.ID not in self.features[parent].tracedReq:
                self.features[parent].tracedReq.append(entry.ID)
            for child in entry.Children:
                child = child.strip()
                #print(f"child feature: {child}")
                if child not in self.features:
                    self.features[child] = RTW_Node(child)
                    if 'abstract_' in child:
                        self.features[child].abstract = True       
                if entry.ID not in self.features[child].tracedReq:
                    self.features[child].tracedReq.append(entry.ID)

 
    # construct the tree for features to show hierarchy of parents and children features relationship 
    # tree node is RTW node of the feature
    def constructRTWTree(self):
        for ID in self.table:
            entry = self.table[ID]
            # exclude constraints, which are tracked using "self.constraints" dictionary 
            if entry.Rule in ['R7', 'R8', 'R9', 'R10']:
                continue
            # identify the root feature
            if entry.Rule == 'R1':
                node = self.features[entry.Children[0]]
                self.root = node
                continue
            node = self.features[entry.Parent]
            if node.rule == "":
                node.rule = entry.Rule
            else:
                # change rule to R6 when combining R2 and R3
                node.rule = 'R6'
            for child in entry.Children:
                childnode = self.features[child.strip()]
                # variable "private" is used to indicate the original parent-child relationship (e.g. R2 and R3)
                # R2 and R3 may be combined and become R6
                childnode.private = entry.Rule 
                childnode.parent = node
                node.children.append(childnode)

    def findRoot(self):
        first_key = list(self.table.keys())[0]
        entry = self.table[first_key]
        node = self.features[entry.Parent]
        while node.parent is not None:
            node = node.parent
        self.root = node
        #self.root.printNode()

    # analyze the RTW tree using "BFS" and set each node's validity
    # call out the node(s) which are not valid (disconnected nodes which have no parent, not appear in the tree)
    def analyzeRTWTree(self):
        if self.root is None:
            self.findRoot()
        priorityQ = []
        priorityQ.append(self.root)
        while len(priorityQ) > 0:
            node = priorityQ.pop(0)
            node.valid = 1
            for childnode in node.children:
                priorityQ.append(childnode)
        for feature in self.features:
            node = self.features[feature]
            if (node.parent == None) and (not node.valid):
                print("Feature: {} is not defined".format(node.name))
                node.printNode()
                # invalidate the entry in the RTW table
                for ID in node.tracedReq:
                    entry = self.table[ID]
                    entry.Valid = 0
                # reconstruct the self.constraints using new information 
                self.constructRTWConstraints()

    # construct feature model constraints in XML form 
    # the syntax is compatible for the featureIDE tool (for feature diagram rendering)
    def constructXMLFeaturModelConstraints(self):
        self.FM_XML.append('\t<constraints>\n') 
        for ID in self.constraints:
            constraint = self.constraints[ID].split("=>")
            self.FM_XML.append('\t\t<rule>\n')
            self.FM_XML.append('\t\t<description>Constraint Requirement: ' + ID + '</description>\n')
            self.FM_XML.append('\t\t\t<imp>\n')
            for c in constraint:
                c = c.replace('(', '')
                c = c.replace(')', '')
                # only handle disjunction for now
                if '||' in c:
                    terms = c.split("||")
                    self.FM_XML.append('\t\t\t\t<disj>\n')
                    for term in terms:
                        if '&&' in term:
                            sub_terms = term.split("&&")
                            self.FM_XML.append('\t\t\t\t\t<conj>\n')
                            for sub_term in sub_terms:
                                if sub_term.strip().startswith('!'):
                                    self.FM_XML.append('\t\t\t\t\t\t\t<not>\n')
                                    self.FM_XML.append('\t\t\t\t\t\t\t<var>' + sub_term.strip().replace('!','') + '</var>\n')
                                    self.FM_XML.append('\t\t\t\t\t\t\t</not>\n')
                                else:
                                    self.FM_XML.append('\t\t\t\t\t\t\t<var>' + sub_term.strip() + '</var>\n')
                            self.FM_XML.append('\t\t\t\t\t\t</conj>\n')
                        else:            
                            if term.strip().startswith('!'):
                                self.FM_XML.append('\t\t\t\t\t<not>\n')
                                self.FM_XML.append('\t\t\t\t\t<var>' + term.strip().replace('!','') + '</var>\n')
                                self.FM_XML.append('\t\t\t\t\t</not>\n')
                            else:
                                self.FM_XML.append('\t\t\t\t\t<var>' + term.strip() + '</var>\n')    
                    self.FM_XML.append('\t\t\t\t</disj>\n')
                else:
                    if c.strip().startswith('!'):
                        self.FM_XML.append('\t\t\t\t<not>\n')
                        self.FM_XML.append('\t\t\t\t<var>' + c.strip().replace('!','') + '</var>\n')
                        self.FM_XML.append('\t\t\t\t</not>\n')
                    else:
                        self.FM_XML.append('\t\t\t\t<var>' + c.strip() + '</var>\n')
            self.FM_XML.append('\t\t\t</imp>\n')
            self.FM_XML.append('\t\t</rule>\n')
        self.FM_XML.append('\t</constraints>\n')
      
    # construct feature model in XML form 
    # the syntax is compatible for the featureIDE tool (for feature diagram rendering)
    def constructXMLFeatureModel(self):
        self.FM_XML = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n',
                    '<featureModel>\n',
                    '\t<properties>\n',
                    '\t\t<graphics key="autolayoutconstraints" value="false"/>\n',
                    '\t\t<graphics key="legendposition" value="1223,200"/>\n',
                    '\t\t<graphics key="legendautolayout" value="false"/>\n',
                    '\t\t<graphics key="showconstraints" value="true"/>\n',
                    '\t\t<graphics key="showshortnames" value="false"/>\n',
                    '\t\t<graphics key="layout" value="horizontal"/>\n',
                    '\t\t<graphics key="showcollapsedconstraints" value="true"/>\n',
                    '\t\t<graphics key="legendhidden" value="false"/>\n',
                    '\t\t<graphics key="layoutalgorithm" value="1"/>\n',
                    '\t</properties>\n',
                    '\t<struct>\n']
        # use dfs to construct the "struct" of feature model
        # "struct" shows the parent-child hierarchical releationship
        self.constructXMLFeatureDiagram(self.root)
        self.FM_XML.append('\t</struct>\n')
        # construct feature model constraints
        self.constructXMLFeaturModelConstraints()
        self.FM_XML.append('</featureModel>\n')


    # use DFS to construct the feature diagram to show the parent-child hierarchical releationship 
    # the syntax is compatible for the featureIDE tool (for feature diagram rendering)
    def constructXMLFeatureDiagram(self, node):
        dict_keyword_start = {'R2': '\t\t<and ', 'R3': '\t\t<and ', 'R4': '\t\t<alt ', 'R5': '\t\t<or ', 'R6': '\t\t<and '}
        dict_keyword_end = {'R2': '\t\t</and>\n', 'R3': '\t\t</and>\n', 'R4': '\t\t</alt>\n', 'R5': '\t\t</or>\n', 'R6': '\t\t</and>\n'}
        if node.isLeaf():
            line = '\t\t\t<feature '
            if node.abstract:
                line = line + 'abstract="true" '
            if node.rule == 'R2' or node.private == 'R2':
                line = line + 'mandatory="true" '
            line = line + 'name="' + node.name + '">\n'
            self.FM_XML.append(line)
            # add requirement ID as description for traceability
            self.FM_XML.append('\t\t\t<description>Requirements: ' + str(node.tracedReq) + '</description>\n')
            self.FM_XML.append('\t\t\t</feature>\n')
            return
        else:
            line = dict_keyword_start[node.rule]
            if node.abstract:
                line = line + 'abstract="true" '
            if node.rule == 'R2' or node.private == 'R2' or node.name == self.root.name:
                line = line + 'mandatory="true" '
            line = line + 'name="' + node.name + '">\n'
            self.FM_XML.append(line)
            # add requirement ID as description for traceability
            self.FM_XML.append('\t\t<description>Requirements: ' + str(node.tracedReq) + '</description>\n')
            for child in node.children:
                # recurcisve call using DFS to build feature diagram
                self.constructXMLFeatureDiagram(child)
            self.FM_XML.append(dict_keyword_end[node.rule])        
      
    # export the feature model to XML file
    def exportFeatureModel2XML(self, filename):
        os.makedirs("feature_model", exist_ok=True)
        with open(f"feature_model/{filename}", 'w') as f:
            for line in self.FM_XML:
                f.write(line)
            f.close()
            
    # construct sentences for feature model (FM)
    # sentence is a propositional logic expression for parent-child relationship or cross-tree constraint releationship
    # the propositional logic definition is based on rules (R2, R3, R4, R5 and R7, R8, R9, R10)
    def constructFMSentences(self):
        self.sat_formula = []
        root = self.root.name
        self.sat_formula.append([Bool(root) == True, self.root.tracedReq]) 
        priorityQ = []
        priorityQ.append(self.root)
        while len(priorityQ) > 0:
            node = priorityQ.pop(0)
            rule = node.rule
            children = []
            for childnode in node.children:
                priorityQ.append(childnode)
                children.append(childnode.name)
                # R6 is combination of R2 and R3, so break down to R2 and R3
                # individual parent-child's rule is stored in private field of child's node 
                if rule == 'R6':
                    self.dict_formula[childnode.private](node.name, [childnode.name], node)  
            # construct the formula for each individual parent-child based on its rule
            if rule != 'R6' and (not node.isLeaf()):
                self.dict_formula[rule](node.name, children, node)

        # add constraints to sat_formula
        self.constructSATConstraints()      
    
    def is_float(self, var):
        try:
            float(var)   # try to convert string to float
            return True
        except ValueError:
            return False

    def get_Z3_variable(self, var_name):
        for op_key in self.operator_map:
            if f"{op_key}" in var_name:
                lhs, rhs = var_name.split(f"{op_key}", 1)
                
                # Decide if it's a string or numeric
                if rhs.isdigit():  # simple integer check
                    rhs_val = int(rhs)
                    lhs_var = Int(lhs)
                elif self.is_float(rhs):
                    rhs_val = float(rhs)
                    lhs_var = Real(lhs)
                else:
                    rhs_val = rhs
                    lhs_var = String(lhs)
                
                # Build the Z3 formula
                if op_key == '==':
                    if lhs_var not in self.feature_assignment_choice:
                        self.feature_assignment_choice[lhs_var] = [rhs_val]
                    else:
                        if rhs_val not in self.feature_assignment_choice[lhs_var]:
                            self.feature_assignment_choice[lhs_var].append(rhs_val)       
                    return lhs_var == (StringVal(rhs_val) if isinstance(lhs_var, str) else rhs_val)
                # elif op_key == '!=':
                #     return lhs_var != (StringVal(rhs_val) if isinstance(lhs_var, str) else rhs_val)
                # elif op_key == '>':
                #     return lhs_var > rhs_val
                # elif op_key == '<':
                #     return lhs_var < rhs_val
                # elif op_key == '>=':
                #     return lhs_var >= rhs_val
                # elif op_key == '<=':
                #     return lhs_var <= rhs_val                
                else:
                    raise ValueError(f"Unsupported operator {op_key}")
        if var_name not in self.feature_assignment_choice:
            self.feature_assignment_choice[var_name] = [True, False]      
        return Bool(var_name)


    # apply formula for R2 rule (mandatory child): parent <=> child
    # convert <=> to => for ACTS tool compatibility, i.e. parent => child, child => parent
    # convert to form comply with z3
    def R2Formula(self, parent, child, node):
        parent_var = self.get_Z3_variable(parent)
        child_var = self.get_Z3_variable(child[0])
        self.sat_formula.append([Implies(parent_var, child_var), node.tracedReq])
        self.sat_formula.append([Implies(child_var, parent_var), node.tracedReq])

    # apply formula for R3 rule (optional child): child => parent
    def R3Formula(self, parent, child, node):
        parent_var = self.get_Z3_variable(parent)
        child_var = self.get_Z3_variable(child[0])
        self.sat_formula.append([Implies(child_var, parent_var), node.tracedReq])

    # apply formula for R4 rule (select exactly only one child, i.e. xor): 
    # parent <=> (childA && !childB && ...) || (!childA && childB && ...)
    # convert <=> to => for ACTS tool compatibility, i.e. 
    # parent => (childA && !childB && ...) || (!childA && childB && ...), 
    # (childA && !childB && ...) || (!childA && childB && ...) => parent
    # and to a form that is complied with z3 (in sat_formulat)
    def R4Formula(self, parent, children, node):
        sat_sentences = []
        n = len(children)
        for i in range(n):
            sat_terms = []
            # R4 (xor): terms = childA or !childA, ...
            #           sentences = (childA && !childB && ...), (!childA && childB && ...)
            for j in range(n):
                child_var = self.get_Z3_variable(children[j])
                sat_term = Not(child_var)
                if i == j:
                    sat_term = child_var
                sat_terms.append(sat_term)
             
            sat_sentence = And(sat_terms)
            sat_sentences.append(sat_sentence)
        
        parent_var = self.get_Z3_variable(parent)
        self.sat_formula.append([Implies(parent_var, Or(sat_sentences)), node.tracedReq])
        self.sat_formula.append([Implies(Or(sat_sentences), parent_var), node.tracedReq])
        
        # add additional constraint: !parent => !childA && !childB && ...
        # sat_terms = []
        # for child in children:
        #     child_var = self.get_Z3_variable(child)
        #     sat_terms.append(Not(child_var))

        # self.sat_formula.append([Implies(Not(parent_var), And(sat_terms)), node.tracedReq])
  
      
    # apply formula for R5 rule (select at least one child, i.e. or): 
    # parent <=> (childA || childB || ...) 
    # convert <=> to => for ACTS tool compatibility, i.e. 
    # parent => (childA || childB || ...) 
    # (childA || childB ||..) => parent
    # and to a form that is complied with z3 (in sat_formulat)
    def R5Formula(self, parent, children, node):
        sat_children = []
        for child in children:
            child_var = self.get_Z3_variable(child)
            sat_children.append(child_var)
        parent_var = self.get_Z3_variable(parent)
        self.sat_formula.append([Implies(parent_var, Or(sat_children)), node.tracedReq])
        self.sat_formula.append([Implies(Or(sat_children), parent_var), node.tracedReq])

    def get_support_features(self):
        support_features = []
        for feature in self.features:
            feature_node = self.features[feature]
            if feature_node.valid != 1:
                continue
            elif 'abstract_' in feature:
                continue
            elif '==' in feature:
                lhs, rhs = feature.split("==")
                lhs = lhs.strip()
                if lhs not in support_features:
                    support_features.append(lhs)
            else:
                if feature not in support_features:
                    support_features.append(feature)
        return support_features

    def showRTWConstraints(self):
        print("Constraints:")
        for ID in self.constraints:
            print(self.constraints[ID])
        print()
        
    def showRTWTable(self):
        print("RTW Entries:")
        for ID in self.table:
            entry = self.table[ID]
            entry.printEntry()
        print()
        
    def showRTWFeatures(self):
        for feature in self.features:
            node = self.features[feature]
            node.printNode()
            
    def showRTWAbstractFeatures(self):
        for feature in self.features:
            node = self.features[feature]
            if node.abstract:
                node.printNode()
    
    def showSATFormula(self):
        print("\nSAT Formula list: ")
        for s in self.sat_formula:
            print(f"   {s[0]}")
        print()
 
    def showSolutions(self):
        print("\nModel Solutions: ")
        for count in range(len(self.solutions)):
            print("solution " + str(count) + " :")
            solutions = self.solutions[count]
            for feature in solutions:
                print('   {0:15s} : {1:5s}'.format(feature, solutions[feature]))   
                
    def showSupportedFeatures(self):
        print("\nSupported Features:")
        for feature in self.support_features:
            print(f"   {feature}")

    def showTestResult(self):
        print("\nTest Result:")
        for status in self.dict_result:
            print("  {}: {}".format(status, self.dict_result[status]))
        print()
  
    def showFeatureAssignmentChoice(self):
        print("\nFeature Assignment Choice:")
        for feature in self.feature_assignment_choice:
            print(f"  {feature}: {self.feature_assignment_choice[feature]}")
        print()

    def showFeaturesNotInCode(self, features_in_code, stat):
        if features_in_code is None:
            return
        total_features_not_in_code = 0
        req_not_covered = []
        print("\nRequired Features NOT in source code:")
        stat.required_features_not_in_code_list.append(["01_Required Features", "Associated Requirement(s)"])
        for feature in self.support_features:
            if feature in features_in_code:
                continue
            for feature_str in self.features:
                if feature in feature_str:
                    feature_node = self.features[feature_str]
                    print(f"   feature: {feature:30s}, requirements: {feature_node.tracedReq}")
                    total_features_not_in_code += 1
                    stat.required_features_not_in_code_list.append([feature, feature_node.tracedReq])
                    req_not_covered = req_not_covered + feature_node.tracedReq
                    break
        total_features = len(self.support_features)
        print(f"Total Required Features in Variability Model: {total_features}")
        stat.total_required_features = total_features
        if total_features != 0:
            print(f"Total Required Feature NOT in source code: {total_features_not_in_code} ({total_features_not_in_code*100/total_features:<0.2f}%)")
            stat.required_features_not_in_code = total_features_not_in_code
            stat.required_features_in_code = stat.total_required_features - stat.required_features_not_in_code
            req_not_covered = list(set(req_not_covered))
            stat.total_requirements = len(self.table)
            total_constraints = 0
            for entry in self.table:
                if self.table[entry].Rule in ['R7', 'R8', 'R9', 'R10']:
                    total_constraints += 1
            print(f"\nTotal textual requirements: {len(self.table)}, constraints: {total_constraints}")
            print(f"Total textual requirements NOT implemented in source code: {len(req_not_covered)}")
            stat.requirements_not_in_code = len(req_not_covered)
            print(f"Textual requirements NOT implemented in source code:")
            req_not_covered.sort()
            for req in req_not_covered:
                print(f"   {req}")
                 
