from z3 import *
from sympy import *
import subprocess
import os
import re
import csv

def getFileLines(filename):
    try:
        with open(filename, 'r', encoding="cp437") as f:
            lines = f.readlines()
        f.close()
        return lines
    except FileNotFoundError:
        raise Exception("File '{}' is not found".format(filename))

def writeFile(filename, lines):
    try:
        with open(filename, 'w') as f:
            f.writelines(lines)
        f.close()
        return lines
    except:
        raise Exception(f"Failed to write file {filename}")

class VarCHEKStat:
    def __init__(self):
        self.total_requirements = 0
        self.requirements_not_in_code = 0
        self.total_required_features =0
        self.required_features_not_in_code = 0
        self.required_features_in_code = 0
        self.loc = 0
        self.var_loc = 0
        self.implemented_lines_not_in_requirements = 0
        self.total_presence_conditions = 0
        self.total_code_features = 0
        self.code_features_in_requirements = 0
        self.code_features_not_in_requirements = 0
        self.requirements_code_consistent = False
        self.code_features_not_in_requirements_list = []
        self.required_features_not_in_code_list = []
        self.presence_conditions_list = []
        self.min_set_configurations = []
        self.inconsistencies = []

    def printStat(self, project):
        bmap = {True: "Yes", False: "No"}
        if self.requirements_code_consistent:
            if not (self.required_features_in_code == self.total_required_features == self.code_features_in_requirements):
                self.requirements_code_consistent = False
        #print(f"Are Variability Requirements and Source Code Consistent? {bmap[self.requirements_code_consistent]}")

        stat_data = [['0_Statistics', project]]
        stat_data.append(["Required Features in Source Code", self.required_features_in_code])
        stat_data.append(["Required Features NOT in Source Code",self.required_features_not_in_code])
        stat_data.append(["Total Required Features",self.total_required_features])
        stat_data.append(["Textual Requirements NOT Implemented in Source Code",self.requirements_not_in_code])
        stat_data.append(["Total Textual Requirements",self.total_requirements])
        stat_data.append(["Features in Source Code Specified in Requirements",self.code_features_in_requirements])
        stat_data.append(["Features in Source Code NOT Specified in Requirements",self.code_features_not_in_requirements])
        stat_data.append(["Total Features in Source Code",self.total_code_features])
        stat_data.append(["Total Presence Conditions in Source Code",self.total_presence_conditions])
        stat_data.append(["Implemented Lines NOT Specified by Requirements",self.implemented_lines_not_in_requirements])
        stat_data.append(["Total variability lines of code",self.var_loc])
        stat_data.append(["Total lines of code",self.loc])
        stat_data.append(["Are Variability Requirements and Source Code Consistent?",bmap[self.requirements_code_consistent]])
        for item in stat_data:
            print(f"{item[0]:60s} {item[1]}")
        with open(f'reports/stat_{project}.csv', 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerows(stat_data)

        if len(self.required_features_not_in_code_list) > 0:
            with open(f'reports/required_features_not_in_code_{project}.csv', 'w', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerows(self.required_features_not_in_code_list)
    
        if len(self.code_features_not_in_requirements_list) > 0:
            with open(f'reports/code_features_not_in_requirements_{project}.csv', 'w', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerows(self.code_features_not_in_requirements_list)
     
        if len(self.presence_conditions_list) > 0: 
            with open(f'reports/presence_condition_{project}.csv', 'w', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerows(self.presence_conditions_list)

        if len(self.min_set_configurations) > 0:
            with open(f'reports/min_set_{project}.csv', 'w', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerows(self.min_set_configurations)

        if len(self.inconsistencies) > 0:
            with open(f'reports/inconsistencies_{project}.csv', 'w', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerows(self.inconsistencies)

class PresenceCondition:    
    def __init__(self, path, filename, filter):
        self.ifnames_file = path + "/ifnames"
        self.path = path
        self.src_list_file = path + '/' + filename
        self.var_list_file = path + "/var_list_file"
        self.filter_files = path + '/' + filter
        self.featuremodel_map_dict = {}
        self.src_list = []
        self.assignment_list = []
        self.assignment_list_weight = []
        self.presence_condition_dict = {}
        self.file_path_list = []
        self.label_prefix = "__"
        self.features_dict = {}
        self.var_file_features = {}
        self.pc_features = {}
        self.var_file_pc = {}
        self.assignment2presence_cond = {}
        self.total_loc = 0
        self.stat = VarCHEKStat()


    def extract_features(self, expression):
        # 1. Define all common comparators
        # We look for the operator, optional spaces, and then the following word/value
        # Pattern: (Operator)(Spaces)(Value)
        comparators_pattern = r'(==|!=|<=|>=|<|>)\s*[a-zA-Z0-9_]+'
        
        # 2. Scrub the values out
        scrubbed_expr = re.sub(comparators_pattern, '', expression)
        
        # 3. Define the pattern for the remaining identifiers
        # Must start with a letter/underscore
        id_pattern = r'[a-zA-Z_.][a-zA-Z0-9_.]*'
        
        # 4. Find all matches in the scrubbed text
        raw_matches = re.findall(id_pattern, scrubbed_expr)
        
        # 5. Clean up: Remove logical keywords and duplicates
        # Note: 'live' is kept because it's usually a boolean feature identifier
        logical_ops = {'and', 'or', 'not', '&&', '||', '!', 'True', 'False'}
        
        identifiers = []
        for item in raw_matches:
            if item.lower() not in logical_ops and item not in identifiers:
                identifiers.append(item)
                
        return identifiers

    def parsePC_Python(self, lines, filename):
        pc = []
        for count, line in enumerate(lines):
            new_line = line.strip()
            if new_line == '1':
                continue
            if new_line in self.presence_condition_dict:
                #self.presence_condition_dict[line_element[2]].append((int(line_element[0]), file_index))
                self.presence_condition_dict[new_line].append(f"{filename}: {count+1}")
            else:
                #self.presence_condition_dict[line_element[2]] = [(int(line_element[0]), file_index)]
                self.presence_condition_dict[new_line] = [f"{filename}: {count+1}"]
            # get the pc in this file
            if new_line not in pc:
                pc.append(new_line)
            
            # extract literals (features) from presence conditions
            features = self.extract_features(new_line)
            # create feature dictionary where key is feature, value if list of files
            for feature in features:
                if feature not in self.features_dict:
                    self.features_dict[feature] = [filename.strip()] 
                elif filename.strip() not in self.features_dict[feature]:
                    self.features_dict[feature].append(filename.strip())   
        return pc


    '''
        # | line of code   | FeatureCopp  |
      ----+----------------+--------------+ 
        A | B              | C            |
        
    A is line number
    B is code at line A
    C is presence condition
    | is the separator
    '''
    def parsePC(self, filename):
        file = filename.strip()
        if file[-3:].lower() == ".py":
            ext = ".py"
        f_name=file.replace(ext, f"{ext}.txt")
        lines = getFileLines(f_name)
        self.total_loc = self.total_loc + len(lines)
        #file_index = self.src_list.index(filename)
        return self.parsePC_Python(lines, filename)

        
    def findPresenceConditions(self):
        for filename in self.src_list:
            # skip header files
            if ".h" in filename:
                continue
            pcs = self.parsePC(filename)
            comparators = ['==', '>', '<', '%', '>=', '<=', '!=', '%=']
            pc_copy = pcs.copy()
            for pc in pc_copy:
                for com in comparators:
                    if com in pc:
                        #print(f"Discard PC: {pc}")
                        pcs.remove(pc)
                        del self.presence_condition_dict[pc]
                        break
            self.var_file_pc[filename] = pcs
        self.sortPresenceConditions()

       
    def sortPresenceConditions(self):
        x = self.presence_condition_dict
        self.presence_condition_dict = dict(sorted(x.items(), key=lambda x: len(x[1]), reverse=True))
 
    def showSrcFiles(self):
        print("\nc file list:")
        for file in self.src_list:
            print("   " + file)
        
    def showPresenceConditions(self):
        print("\nPresence Conditions: ")
        for pc in self.presence_condition_dict:
            print("   " + pc)
            
    def showPresenceConditionsMap(self):
        print("\nPresence Conditions: ")
        for entry in self.presence_condition_dict:
            print(f'  {entry:20s}')
            lines = self.presence_condition_dict[entry]
            for line in lines:
                print(f'    {line}')
                
    def showPresenceConditionsStat(self):
        if len(self.presence_condition_dict) > 0:
            self.stat.presence_conditions_list.append(['01_Presence Condition', '02_Total Lines in Code', '03_Line Coverage Precentage'])
        print("Presence Conditions Statistics: ")
        self.var_total_lines = 0
        for pc in self.presence_condition_dict:
            self.var_total_lines = self.var_total_lines + len(self.presence_condition_dict[pc])
        print("  {:120s} {:^20s} {:^20s}".format("Presence Conditions", "Line Coverage", "Line Coverage %"))
        for pc in self.presence_condition_dict:
            lines = len(self.presence_condition_dict[pc])
            lines_percentage = round(lines/self.var_total_lines*100,2)                     
            print("  {:120s} {:^20d} {:^20.2f}".format(pc, lines, lines_percentage))
            self.stat.presence_conditions_list.append([pc, lines, lines_percentage])
        print(f"Total Presence Conditions: {len(self.presence_condition_dict)}")
        self.stat.total_presence_conditions = len(self.presence_condition_dict)
        print(f"Total lines in variability source code: {self.var_total_lines}")
        self.stat.var_loc = self.var_total_lines
        print(f"total lines in source code: {self.total_loc}")
        self.stat.loc = self.total_loc

    def discardNumericals(self):
        discard_pc = []
        saved_pc = self.presence_condition_dict.copy()
        matches = ['==', '>', '<', '%', '>=', '<=', '!=', '%=']
        #matches = ['==', '>', '<', '%', '>=', '<=', '!=', '%=', "0&&", "0 &&", "&&0", "&& 0"]
        for pc in saved_pc:
            for term in matches:
                if term in pc:
                    discard_pc.append(pc)
                    del self.presence_condition_dict[pc]
                    break

    def showAssignments(self):
        print("\nAssignments for Presence Conditions")
        for assignment in self.assignment_list:
            print("   {:60s}  {:6d}".format(str(assignment[0]), assignment[1]))

    def showAssignmentsWeight(self):
        print("\nAssignments (weight) for Presence Conditions")
        for assignment in self.assignment_list_weight:
            print("   {:60s}  {:6d}".format(str(assignment[0]), assignment[1]))


    def get_variable_count(self, formula):
        disj = str(formula) 
        disj = disj.split('|')
        disj_count = len(disj)
        mix_count = 0
        for var in disj:
            conj = var.split('&')
            mix_count = mix_count + len(conj)
        if disj_count == mix_count:
            return 1
        else:
            return mix_count

    def convert2DNF(self, pc):
        feature_list = {}
        modified_pc = pc
        filters = ['==1', '~=0', ' & ~0', '~0 & ', ' & 1', '1 & ', '0 | ', ' | 0', '~1 | ', ' | ~1', ' & ~(0)', ' & (1)', '(1) & ', '~(0) & ', '(0) | ', ' | (0)', '~(1) | ', ' | ~(1)']
        for filter in filters:
            modified_pc = modified_pc.replace(filter, '')

        sentence = modified_pc
        matches = ['(', ')', '&', '|']
        for c in matches:
            sentence = sentence.replace(c, '')
        terms = sentence.split()
        for i, term in enumerate(terms):
            if '==0' in term:
                terms[i] = terms[i].replace('==0', '')
                modified_pc = modified_pc.replace('==0', '')
                modified_pc = modified_pc.replace(terms[i], '~' + terms[i])
            if '~=1' in term:
                terms[i] = terms[i].replace('~=1', '')
                modified_pc = modified_pc.replace('~=1', '')
                modified_pc = modified_pc.replace(terms[i], '~' + terms[i])
  
        for term in terms:
            if '~' in term:
                term = term.replace('~', '')
            feature = term
            if feature not in feature_list:
                feature_list[feature] = (Symbol(feature.strip()))

        if (" & ~1" in modified_pc) or ("~1 & " in modified_pc) or (modified_pc == '?') or (modified_pc == '') or (modified_pc == ' '):
            return None, None
        try:
            formula = sympify(modified_pc, locals=feature_list)
        except:
            print(f"Sympify Error: pc: {modified_pc}")
            return None, None
        var_count = self.get_variable_count(formula)
        if var_count < 8:
            dnf = to_dnf(formula, simplify=True, force=True)
            return dnf, feature_list
        else:
            print(f"Warning: More than 8 variables in DNF, formula: {formula}, skipped")
            return None, None     

    def _getAssignments(self, sentence):
        assignment = []
        s = sentence
        s = s.replace('(','')
        s = s.replace(')','')
        terms = s.split(' & ')
        for term in terms:
            if '~' in term:
                assignment.append(Bool(term.replace('~', '').strip()) == False)
            else:
                assignment.append(Bool(term.strip()) == True)
        return assignment

    def getAssignments(self):       
        self.assignment_list = []
        self.assignment_list_weight = []
        self.assignment2presence_cond = {}
        assignments_dict = {}
        for ori_pc in self.presence_condition_dict:
            pc = ori_pc
            source_lines = self.presence_condition_dict[pc]
            lines = len(source_lines) 
            pc = pc.replace("&&", " & ")
            pc = pc.replace("||", " | ")
            pc = pc.replace("!", "~")
            dnf, feature_list = self.convert2DNF(pc)
            if dnf is None or dnf == -1:
                continue
            else:
                features = []
                for feature in feature_list:
                    features.append(feature)
                self.pc_features[ori_pc] = features
            sentences = str(dnf).split(' | ')
            for sentence in sentences:
                assignment = self._getAssignments(sentence.strip())
                key = str(assignment)
                if key not in assignments_dict:
                    assignments_dict[key] = [assignment, lines, source_lines]
                    self.assignment2presence_cond[key] = ori_pc
                else:
                    source_lines_exist = assignments_dict[key][2]
                    assignments_dict[key] = [assignment, assignments_dict[key][1] + lines, source_lines + source_lines_exist] 
        
        for key in assignments_dict:
            lines = assignments_dict[key][1]
            assignments = assignments_dict[key][0]
            source_lines = assignments_dict[key][2]
            weight = len(assignments) + lines*5 
            self.assignment_list.append([assignments, lines, source_lines])
            self.assignment_list_weight.append([assignments, weight, source_lines])
        self.assignment_list_weight = sorted(self.assignment_list_weight, key=lambda x: x[1], reverse=True)

    def reverseFeatureMap(self, feature_map):
        self.featuremodel_map_dict = feature_map

    def showFeatureModelMap(self):
        print("\nFeature: Code Variable to Feature Model Map")
        for label in self.featuremodel_map_dict:
            print(f"   {label} : {self.featuremodel_map_dict[label]}")

    def findFeaturesNotInFeatureModel(self):
        print("\nFeatures in Source Code NOT specified in Requirements:")
        total_features = len(self.features_dict)
        total_features_not_in_fm = 0
        self.feature_not_in_code_coverage = {}
        feature_list = []
        for feature in self.features_dict:
            feature_list.append(feature)
            if feature not in self.featuremodel_map_dict:
                feature = feature.strip()
                if ("HEADER" not in feature) and ("_H" not in feature[-2:]):
                    lines = 0
                    for pc in self.presence_condition_dict:
                        if feature in pc:
                            lines += len(self.presence_condition_dict[pc])
                    if lines > 0: 
                        self.feature_not_in_code_coverage[feature] = lines
                        total_features_not_in_fm += 1
                    else:
                        total_features -= 1
                else:
                    total_features -= 1

        x = self.feature_not_in_code_coverage
        self.feature_not_in_code_coverage = dict(sorted(x.items(), key=lambda item: item[1],reverse=True))
        total_lines = 0
        if len(self.feature_not_in_code_coverage) > 0:
            self.stat.code_features_not_in_requirements_list.append(["01_Features in Source Code", "Code Lines by Feature", "Feature Codes %"])
        for feature in self.feature_not_in_code_coverage:
            coverage = round(self.feature_not_in_code_coverage[feature]*100/self.var_total_lines, 2)
            print(f"     {feature:30s}: lines: {self.feature_not_in_code_coverage[feature]:^5d}, coverage: {coverage:<.2f}%")
            self.stat.code_features_not_in_requirements_list.append([feature, self.feature_not_in_code_coverage[feature], coverage])
            total_lines = total_lines + self.feature_not_in_code_coverage[feature]
        if total_features == 0:
            print(f"Total Features in Source Code NOT specified in Requirements: {total_features_not_in_fm}")
        else:
            print(f"Total Features in Source Code NOT specified in Requirements: {total_features_not_in_fm} ({total_features_not_in_fm*100/total_features:<.2f}%)")
        self.stat.code_features_not_in_requirements = total_features_not_in_fm
        print(f"Total lines not covered by Requirements: {total_lines}")
        self.stat.implemented_lines_not_in_requirements = total_lines
        print(f"Total Features in Source Code: {total_features}")
        self.stat.total_code_features = total_features
 

    def findFeaturesInFeatureModel(self):
        print("\nFeatures in Source Code specified in Requirements:")
        # total_features = len(self.features_dict)
        total_features_in_fm = 0
        for feature in self.features_dict:
            if feature in self.featuremodel_map_dict:
                total_features_in_fm += 1
                print(f"    {feature}")
        print(f"Total Features in Source Code specified in Requirements: {total_features_in_fm}")
        self.stat.code_features_in_requirements = total_features_in_fm
               
    
    


        


            
