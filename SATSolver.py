from z3 import *
import csv

class SATSolver:    
    def __init__(self, rtw, pc, project="axtls"):
        self.feature_model = rtw.sat_formula
        self.model = None
        self.solver = None
        self.presenceConditionAssignments = []
        self.configSet = []
        self.config_table = {}
        self.code_features = pc.features_dict
        self.assignment2presence_cond = {}
        self.project = project
        self.pc = pc
        self.rtw = rtw

    def buildModel(self):
        self.solver = Solver()
        for item in self.feature_model:
            sentence = item[0] 
            self.solver.add(sentence)

        # slicing FM, only for AxTLS
        # if self.project == "axtls":
        #     self.solver.add(Bool('CONFIG_PLATFORM_LINUX') == True)
        #     self.solver.add(Bool('_WIN32_WCE') == False)
        #     self.solver.add(Bool('WIN32') == False)
        #     self.solver.add(Bool('__cplusplus') == False)

        # elif self.project == "busybox-editors":
        #     # for busybox editors
        #     self.solver.add(Bool('ENABLE_FEATURE_VI_CRASHME') == False)
        # elif self.project == "busybox-coreutils":
        #     # for busybox coreutils
        #     self.solver.add(Bool('VERSION_WITH_WRITEV') == False)
        #     self.solver.add(Bool('ENABLE_LFS') == True)
        #     self.solver.add(Bool('S_TYPEISTMO') == False)
        
    def runModelCheck(self):
        self.model = None
        r = self.solver.check()
        if r == sat:
            self.model = self.solver.model()
        return r

    def printModel(self):
        print(f"\nModel: ")
        print(self.model)    

    def verify_req_id(self, req_ids, presence_condition):
        rtw_table = self.rtw.table
        features = self.pc.getFeatures(presence_condition)
        new_req_ids = []
        for req_id in req_ids:
            rtw_entry = rtw_table[req_id]
            entry_features = [rtw_entry.Parent] + rtw_entry.Children
            if any(feature in entry_features for feature in features):
                new_req_ids.append(req_id)
        return new_req_ids

    def showInconsistencies(self, inconsistencies_dict):
        stat = self.pc.stat
        for i, pc in enumerate(inconsistencies_dict):
            i_dict = inconsistencies_dict[pc]
            stat.inconsistencies.append([f"{i+1}) Presence Condition:", pc])
            stat.inconsistencies.append(["   Assignments:", i_dict['Assignments']])
            src_locations = i_dict["Source Code location"]
            for src_location in src_locations:
                stat.inconsistencies.append(["   Source Code location:", src_location])
            requirement_ids = i_dict["Requirement ID"]
            requirement_sentences = i_dict["Requirement Sentence"]
            for i, req_id in enumerate(requirement_ids):
                sentence = requirement_sentences[i]
                req_id = self.verify_req_id(req_id, pc)
                stat.inconsistencies.append(["   Conflicted Requirement ID:", req_id])
                stat.inconsistencies.append(["   Conflicted Requirement Sentence:", sentence])
            if "Dead Code" in i_dict["Requirement Sentence"]:
                stat.inconsistencies.append(["   Dead Code"])
        print()
        for item in stat.inconsistencies:
            print(item)
        print()

    def evalPresenceCondition(self, presence_cond_assignments, assignment2presence_cond):
        self.assignment2presence_cond = assignment2presence_cond
        status = []
        self.presenceConditionAssignments = []
        unsat_presence_conditions = []
        for item in presence_cond_assignments:
            self.presenceConditionAssignments.append(item[0])  
        for pc in self.presenceConditionAssignments:
            self.buildModel()
            for assignment in pc:
                self.solver.add(assignment)
            status.append(self.runModelCheck())

        #print(status)
        print("\nConsistency Checking:")
        count = 1
        inconsistencies_dict = {}
        if unsat in status:
            for i, s in enumerate(status):
                #index = status.index(unsat)
                if s == unsat:
                    key = str(presence_cond_assignments[i][0])
                    #print(f"Presence Condition: {self.assignment2presence_cond[key]} is not consistent with Variability Model")
                    #print(f"       Assignments: {presence_cond_assignments[i][0]}")
                    inconsistencies_dict[self.assignment2presence_cond[key]] = {"Assignments": presence_cond_assignments[i][0]}
                    count += 1
                    #print(f"Source Code:")
                    previous_line = -1
                    first_sequential = True
                    code_strings = []
                    for loc in presence_cond_assignments[i][2]:
                        string = loc.split(":")
                        current_line = int(string[1].strip())
                        if current_line != previous_line + 1:
                            code_strings.append(loc)
                            first_sequential = True
                        else:
                            last_entry = len(code_strings) - 1
                            if first_sequential:
                                code_strings[last_entry] = code_strings[last_entry] + f" - {current_line}"    
                                first_sequential = False
                            else:
                                code_strings[last_entry] = code_strings[last_entry].replace(str(previous_line), str(current_line))
                        previous_line = current_line
                    if len(code_strings) > 0:
                        inconsistencies_dict[self.assignment2presence_cond[key]]["Source Code location"] = []
                    for string in code_strings:
                        #print(f"       {string}")
                        inconsistencies_dict[self.assignment2presence_cond[key]]["Source Code location"].append(string)
                    unsat_presence_conditions.append([i, presence_cond_assignments[i][0]])
        else:
            print(f"Presence Conditions are consistent with Variability Model\n")
            self.pc.stat.requirements_code_consistent = True
        
        self.findUnsatConflict(unsat_presence_conditions, assignment2presence_cond, inconsistencies_dict)

        i = len(unsat_presence_conditions) - 1
        while i >= 0:
            # remove unsat presence condition
            index = unsat_presence_conditions[i][0]
            print(f"Remove 'unsat' presence condition assignments: {self.presenceConditionAssignments.pop(index)}")
            i -= 1    
        print()
        self.showInconsistencies(inconsistencies_dict)
        

    def findUnsatConflict(self, unsat_presence_conditions, assignment2presence_cond, inconsistencies_dict):
        for unsat in unsat_presence_conditions:
            sentence_check_list = []
            pc = unsat[1]
            key = str(pc)
            features = []
            self.solver = Solver()
            for assignments in pc:
                feature, val = str(assignments).split(' == ')
                feature = feature.strip()
                if feature not in features:
                    features.append(feature)

            for item in self.feature_model:
                sentence = item[0]
                match = False
                for feature in features:
                    if feature in str(sentence):
                        sentence_check_list.append(item) 
                        match = True
                        break
                if not match:
                    self.solver.add(sentence)

            # sanity test
            if self.runModelCheck() != sat:
                raise Exception(f"Unsat error")

            for assignments in pc:
                self.solver.add(assignments)

            if self.runModelCheck() == sat:
                print(f"\nPresence Condition: {assignment2presence_cond[key]} is conflicted with")
                if len(sentence_check_list) > 0:
                    inconsistencies_dict[self.assignment2presence_cond[key]]["Requirement ID"] = []
                    inconsistencies_dict[self.assignment2presence_cond[key]]["Requirement Sentence"] = []
                for item in sentence_check_list:
                    solver_copy = Solver()
                    solver_copy.add(self.solver.assertions())
                    sentence = item[0]
                    #self.solver.add(sentence)
                    #if self.runModelCheck() != sat:
                    solver_copy.add(sentence)
                    if solver_copy.check() != sat:
                        #print(f"Requirements: {item[1]}")
                        #print(f"    Sentence: {sentence}")
                        inconsistencies_dict[self.assignment2presence_cond[key]]["Requirement ID"].append(item[1])
                        inconsistencies_dict[self.assignment2presence_cond[key]]["Requirement Sentence"].append(sentence)
                        #break
            else:
                print(f"\nPresence Condition: {assignment2presence_cond[key]} is Dead Code")
                inconsistencies_dict[self.assignment2presence_cond[key]]["Requirement ID"] = []
                inconsistencies_dict[self.assignment2presence_cond[key]]["Requirement Sentence"] = ["Dead Code"]

    def findMinConfigSet(self):
        # create check list and check all items with 'O'
        pc_check_list = []
        self.configs_pc = []
        for count in range(len(self.presenceConditionAssignments)):
            pc_check_list.append('O')
            #print(self.presenceConditionAssignments[count])

        while 'O' in pc_check_list:
            self.buildModel()
            push_pc = []
            # config_pc is list of pc in the config
            config_pc = []
            while 'O' in pc_check_list:
                index = pc_check_list.index('O')
                pc = self.presenceConditionAssignments[index]
                for assignment in pc:
                    self.solver.add(assignment)
                    push_pc.append(assignment)
                push_count = len(pc)
                if self.runModelCheck() == sat:
                    # check the item with 'S' to indicate the associated presence condition assignments are satisfied
                    pc_check_list[index] = 'S'
                    config_pc.append(self.assignment2presence_cond[str(pc)])
                else:
                    # if unsatisfied, temporarily check the item with 'X' 
                    pc_check_list[index] = 'X'
                    # rebuild the model with the unsatisfied assignments excluded
                    self.buildModel()
                    push_count = push_count*-1
                    push_pc = push_pc[:push_count]
                    for assignment in push_pc:
                        self.solver.add(assignment) 
                    # sanity check to make sure the model is satisfied without the unsat assignments
                    if self.runModelCheck() != sat:
                        print("Error in backtracking")   
            # add the solution to the list
            self.configSet.append(self.model)
            #print(pc_check_list)
            self.configs_pc.append(config_pc)
            # revert back all 'X' item to 'O' and repeat the process
            while 'X' in pc_check_list:
                index = pc_check_list.index('X')
                pc_check_list[index] = 'O'


    def getMinConfigSet(self):
        self.feature_not_in_code = []
        self.findMinConfigSet()
        self.config_table = {}
        config_numbers = len(self.configSet)
        if config_numbers != 0:
            for count, config in enumerate(self.configSet):
                for feature in config:
                    feature_str = str(feature)
                    if feature_str not in self.code_features:
                        #print(f"Min set: discard feature: {feature_str} (not in code)")
                        if feature_str not in self.feature_not_in_code:
                            self.feature_not_in_code.append(feature_str)
                        continue
                    if feature_str not in self.config_table:
                        if count == 0:   
                            self.config_table[feature_str] = [str(config[feature])]
                        else:
                            self.config_table[feature_str] = ['any'] * count
                            self.config_table[feature_str].append(str(config[feature]))
                    else:
                        for i in range(len(self.config_table[feature_str]), count):
                            self.config_table[feature_str].append('any')
                        self.config_table[feature_str].append(str(config[feature]))  
            for feature in self.config_table:
                settings = self.config_table[feature]
                for i in range(len(settings), config_numbers):
                    self.config_table[feature].append('any')    

    def printConfigTable(self, feature_map, stat):
        if len(self.configSet) > 0:
            stat.min_set_configurations.append(['01_Feature'])
        print("\n  %40s " % "Feature", end =" ")
        for i in range(len(self.configSet)):
            s = "cfg" + str(i+1)
            print(" %6s " % s, end =" ")
            stat.min_set_configurations[0].append(s)
        user_config_table = {}
        code_config_table = {}
        for feature in self.config_table:
            if feature in feature_map:
                user_config_table[feature] = self.config_table[feature]
            else:
                code_config_table[feature] = self.config_table[feature]
        print()
        for feature in user_config_table:
            minset_entry = [feature]
            print("  %40s " % feature, end =" ")
            for count, setting in enumerate(user_config_table[feature]):
                print(" %6s " % setting, end =" ")
                minset_entry.append(setting)
            print()
            stat.min_set_configurations.append(minset_entry)
        for feature in code_config_table:
            minset_entry = [feature]
            print("  %40s " % feature, end =" ")
            for count, setting in enumerate(code_config_table[feature]):
                print(" %6s " % setting, end =" ")
                minset_entry.append(setting)
            print()
            stat.min_set_configurations.append(minset_entry)
            


        
        
