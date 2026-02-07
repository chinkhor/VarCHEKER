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

    # delete all *.cpp1/*.c1 and *.txt files generated for analysis
    def cleanup(self):
        file_list = getFileLines(self.var_list_file)
        if len(file_list) > 0:
            for file in file_list:
                rm_file = file.strip()
                if rm_file[-2:].lower() == ".c":
                    ext = ".c"
                elif rm_file[-4:].lower() == ".cpp":
                    ext = ".cpp"
                elif rm_file[-2:].lower() == ".h":
                    ext = ".h"
                    continue
                else:
                    raise Exception(f"cleanup: File extension of {rm_file} is not supported")
                
                rm_file = rm_file.strip().replace(ext, f"{ext}.txt")
                command = f"rm {rm_file}"
                os.system(command)

    def runPCLocator(self):
        print(f"Variability source code:")
        for file in self.src_list:
            input_file = file.strip()
            if file[-2:].lower() == ".c":
                ext = ".c"
            elif file[-4:].lower() == ".cpp":
                ext = ".cpp"
            elif file[-2:].lower() == ".h":
                ext = ".h"
                continue
            else:
                raise Exception(f"runPCLocator: File extension of {file} is not supported")
            output_file = file.strip().replace(ext, f"{ext}.txt")
            print(f"   {file}")
            command = f"java -jar PCLocator/PCLocator.jar --annotator featurecopp --raw {input_file} > {output_file}"
            os.system(command)

    # TO-DO: expand to cover "!= false" and "== false"
    def transform_line(self, line):
        new_line = line
            # change '(A != true)' to !(A)
        pattern = "!="
        if pattern in new_line:
            split_words = new_line.split("!=")
            for i in range(len(split_words)-1):
                index = split_words[i].rfind('(')
                split_words[i] = split_words[i][:index] + '!' + split_words[i][index:]
            new_line = "!=".join(split_words)
            new_line = new_line.replace("!=", "==")
        # filter '== true'
        pattern = "=="
        word = pattern
        while pattern in new_line:
            index = new_line.index(pattern)
            if new_line[index + len(pattern)] == " ":
                word = word + " "
            if new_line[index - 1] == " ":
                word = " " + word
            if word + "true" in new_line:
                new_line = new_line.replace(word + "true", "")
                word = pattern
            elif "true" not in new_line:
                return new_line
            else:
                raise Exception(f"transform line error: {new_line}")
        return new_line
    
    # transform_file is customized for cFS
    def transform_file(self):
        file_list = getFileLines(self.src_list_file)
        if file_list is not None:
            for file in file_list:
                new_lines = []
                file = file.strip()
                lines = getFileLines(file)
                for line in lines:
                    if "#if" in line:
                        new_line = self.transform_line(line)
                        new_lines.append(new_line)
                    else:
                        new_lines.append(line)
                if not all(x == y for x, y in zip(lines, new_lines)):
                    writeFile(file, new_lines)

    def runIfNames(self):
        file_list = getFileLines(self.src_list_file)
        if file_list is not None:
            features_dict = {}
            # run ifnames per file, highly not optimal, need to optimize later
            for file in file_list:
                result = subprocess.run(['ifnames', file.strip()], stdout=subprocess.PIPE)
                lines = result.stdout.decode('utf-8').splitlines()
                for line in lines:
                    items = line.split()
                    if len(items) > 1:
                        feature = items[0]
                        files = items[1:]
                        if feature == 'true' or feature == 'false':
                            continue
                        if feature not in features_dict:
                            features_dict[feature] = files
                        else:
                            for f in files:
                                if f not in features_dict[feature]:
                                    features_dict[feature].append(f)
            self.features_dict = features_dict

    def addFile2VarList(self, filename, filehandler):
        file = filename.strip()
        filehandler.write(f"{file}\n")   
        self.src_list.append(file) 

    # save the variability features and files identified by ifnames tool
    def saveVarFeaturesAndFiles(self):
        # save the output of ifnames to file
        # form: feature <file list>
        variation_files = {}
        with open(self.ifnames_file, 'w') as f:
            for feature in self.features_dict:
                files = " ".join(str(x) for x in self.features_dict[feature])
                f.write(f"{feature} {files}\n")
                for file in self.features_dict[feature]:
                    if file not in variation_files:
                        variation_files[file] = [feature]
                    else:
                        variation_files[file].append(feature)
            f.close()
        # save the cpp files that support variability to var_list
        with open(self.var_list_file, 'w') as f:
            self.src_list = []
            try:
                filter_files = getFileLines(self.filter_files)
            except:
                filter_files = []
            # filter out file(S) that has code that is not supported by PCLocator
            variation_files_copy = variation_files.copy()
            for file in variation_files_copy:
                if len(filter_files) > 0:
                    flag = False
                    for filter_file in filter_files:
                        if file.strip() == filter_file.strip():
                            print(f"Filter file: {file}")
                            flag = True
                            break
                        # filter_file is a directory
                        elif filter_file.strip() in file.strip():
                            print(f"Filter directory: {filter_file}, file: {file}")
                            flag = True
                            break
                    if not flag:
                        self.addFile2VarList(file, f)
                    else:
                        print(f"delete {file}")
                        del variation_files[file]
                else:
                    self.addFile2VarList(file, f)
                    
            f.close()
        self.var_file_features = variation_files

    '''
    command: java -jar PCLocator.jar --annotator featurecopp <filename>
    output format of PCLocater (analyzer = FeatureCopp) 
        # | line of code   | FeatureCopp  |
      ----+----------------+--------------+ 
    '''    
    def isHeaderValid(self, line):
        header = [] 
        for l in line:
            header.append(l.strip())
        return (len(header) >= 3 and header[0] == '#' and header[1] == "line of code" and header[2] == "FeatureCoPP")

    def process_precedence(self, line):
        # precedence order: &&, or 
        # A && B or C == (A && B) or C
        if ' or ' in line and '&&' in line:
            or_terms = line.split(' or ')
            for i, or_term in enumerate(or_terms):
                if '&&' in or_term:
                    or_terms[i] = f"({or_terms[i]})"
            return ' || '.join(or_terms)
        else:
            return line.replace(' or ', ' || ')

    def process_logic(self, line):
        new_line = line
        clause_sub = {}
        count = 1
        if ' or ' in line and '&&' in line:
            new_line = line
            if '(' in line:
                word = []
                stack = []
                for c in line:
                    if c != ')':
                        stack.append(c)
                    else:
                        word = stack.pop()
                        while '(' not in word:
                            word = word + stack.pop()
                        # reverse the word
                        word = word[::-1]
                        # remove the first '(' character
                        word = self.process_precedence(word[1:])
                        # substitute inner () with ##{count}
                        clause_sub[f"##{count}"] = f"({word})"
                        stack.append("##")
                        stack.append(str(count))
                        count += 1
                new_line = ""
                while len(stack) > 0:
                    new_line = new_line + stack.pop()
                new_line = new_line[::-1]
            new_line = self.process_precedence(new_line)
            
            # replace substitutes
            num = count - 1
            while num > 0:
                key = f"##{num}"
                new_line = new_line.replace(key, clause_sub[key]) 
                num -= 1
        new_line = new_line.replace('&&', ' && ')
        new_line = new_line.replace(' or ',' || ')
        return new_line

    def is_substring(self, prev, cur):
        index = cur.find(prev, 0)
        if index == -1:
            return False
        end = index + len(prev)
        if end >= len(cur):
            return False
        else:
            match = re.search('[a-zA-Z0-9_]', cur[end])
            return not match

    def getFeatures(self, line):
        features = []
        new_line = line
        new_line = new_line.replace('(','')
        new_line = new_line.replace(')','')
        new_line = new_line.replace('!','')
        elements = new_line.split('&&')
        for element in elements:
            term = element.split('||')
            for feature in term:
                features.append(feature.strip())
        return list(set(features))

    def strip(self, pc):
        new_pc = pc
        features = self.getFeatures(new_pc)
        for feature in features:
            new_pc = new_pc.replace(f"({feature})", feature)
            new_pc = new_pc.replace(f"({feature})", feature)
            new_pc = new_pc.replace(f"(!{feature})", f"!{feature}")
        return new_pc

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

    def parsePC_C(self, lines, filename):
        pc = []
        previous_line = "???"
        for count, line in enumerate(lines):
            line = line.strip()
            if previous_line != line and previous_line in line and self.is_substring(previous_line, line):
                line = line.replace(previous_line, f"({previous_line})", 1)
            # logical or symbol || will create confusion with sperator '|'. Change '||' to 'or'
            new_line = line.replace("||", " or ")
            new_line = new_line.strip()
            if (new_line != '1' and new_line != '0' and ("&&0" not in new_line) and ("0&&" not in new_line)) and new_line != '?':
                new_line = self.process_logic(new_line)
                # remove unnecessary ()
                new_line = self.strip(new_line)
                if new_line in self.presence_condition_dict:
                    #self.presence_condition_dict[line_element[2]].append((int(line_element[0]), file_index))
                    self.presence_condition_dict[new_line].append(f"{filename}: {count+1}")
                else:
                    #self.presence_condition_dict[line_element[2]] = [(int(line_element[0]), file_index)]
                    self.presence_condition_dict[new_line] = [f"{filename}: {count+1}"]
                # get the pc in this file
                if new_line not in pc:
                    pc.append(new_line)
            previous_line = line
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
        python = False
        if file[-2:].lower() == ".c":
            ext = ".c"
        if file[-2:].lower() == ".h":
            ext = ".h"
            return
        elif file[-4:].lower() == ".cpp":
            ext = ".cpp"
        elif file[-3:].lower() == ".py":
            ext = ".py"
            python = True
        f_name=file.replace(ext, f"{ext}.txt")
        lines = getFileLines(f_name)
        self.total_loc = self.total_loc + len(lines)
        #file_index = self.src_list.index(filename)
        if python:
            return self.parsePC_Python(lines, filename)
        else:
            return self.parsePC_C(lines, filename)

    def isHeader(self, pc):
        if "&&" in pc or "||" in pc:
            return False
        else:
            if "!" in pc and ("HEADER" in pc or "_H)" in pc or "_H\n" in pc):
                return True
            else:
                return False

    # def isInternalCodeVariables(self, pc):
    #     clauses = pc.split('&&')
    #     for _clauses in clauses:
    #         clause = _clauses.split('||')
    #         for term in clause:
    #             if "CONFIG" in term:
    #                 return False
    #     return True
        
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


    def findFeatureSymbol(self, pc):
        feature_list = {}
        sentence = pc
        matches = ['(', ')', '&', '|', '~']
        for c in matches:
            sentence = sentence.replace(c, '')
        terms = sentence.split()
        for term in terms:
            if term not in feature_list:
                feature_list[term] = Symbol(term.strip())
        return feature_list    

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
               
    
    


        


            
