from RTW import RTW
from PresenceCondition import PresenceCondition
from SATSolver import SATSolver
import time
import os
from PresenceCondition import getFileLines
import subprocess
import re
busybox_version = "busybox-1.37.0"

def restore_file(files):
    for file in files:
        command = f"mv {file}.original {file}"
        os.system(command)
        command = f"rm {file}.transform"
        os.system(command)

def sort_pc_in_file(file_pc, pc_features):
    for file in file_pc:
        file_pc[file] = sorted(file_pc[file], key=lambda x: len(pc_features[x]), reverse=True)

def isHeader(feature):
    if ("HEADER" in feature or "_H\n" in feature):
        return True
    else:
        return False

def findFeatureCount(line):
    if '&&' not in line and '||' not in line:
        return 1
    else:
        count = 0
        elements = line.split('&&')
        for element in elements:
            term = element.split('||')
            count += len(term)
        return count

def getFeatures(line):
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


def getPCEval(pc, internal_features, project):
    features = getFeatures(pc)
    new_pc = pc
    feature_bin = []
    for feature in features:
        if feature in internal_features and feature in new_pc:
            start = 0
            while True:
                index = new_pc.find(feature, start)
                if index == -1:
                    break
                end = index + len(feature)
                if end >= len(new_pc):
                    unmatch = False
                else:
                    unmatch = re.search('[a-zA-Z0-9_]', new_pc[end])
                if not unmatch:
                    new_pc = new_pc[:index] + new_pc[index:].replace(feature, internal_features[feature],1)
                    start = index
                else:
                    start = end
        else:
            feature_bin.append(feature)
    if new_pc != pc and project == "axtls":
        for feature in feature_bin:
            if feature in new_pc:
                start = 0
                while True:
                    index = new_pc.find(feature, start)
                    if index == -1:
                        break
                    end = index + len(feature)
                    if end >= len(new_pc):
                        unmatch = False
                    else:
                        unmatch = re.search('[a-zA-Z0-9_]', new_pc[end])
                    if not unmatch:
                        new_pc = new_pc[:index] + new_pc[index:].replace(feature, f"defined({feature})", 1)
                    start = index + len(feature) + len("defined()")
    return new_pc        

def get_internal_features(kconfig_features, config_table, cfg_set=0):
    settings_map = {'True' : '1', 'False': '0'}
    internal_features = {}
    for feature in config_table:
        if feature not in kconfig_features:
            setting = config_table[feature][cfg_set] 
            if setting != 'any':
                internal_features[feature] = settings_map[config_table[feature][cfg_set]]
    print(f"internal features:")
    for feature in internal_features:
        print(f"    feature: {feature}, setting: {internal_features[feature]}")   
    return internal_features 

def get_axtls_kconfig_features(config_table, cfg_set=0):
    settings_map = {'True' : '1', 'False': '0', 'any': ''}
    cwd = os.getcwd()
    os.chdir(f"{cwd}/axtls-code/config")
    lines = getFileLines("config.h")
    os.system("cp config.h config.h.old")
    new_lines = []
    kconfig_features = []
    for line in lines:
        if "#define" in line:
            items = line.split()
            feature = items[1]
            if feature in config_table:
                kconfig_features.append(feature)
                setting = config_table[feature][cfg_set]  
                if settings_map[setting] != items[2]:
                    if settings_map[setting] == '0':
                        new_lines.append(f"#undef {feature}\n")
                        continue
                    elif settings_map[setting] == '1':       
                        new_lines.append(f"#define {feature} 1\n")
                        continue
        elif "#undef" in line:
            items = line.split()
            feature = items[1]
            if feature in config_table:
                kconfig_features.append(feature)
                setting = config_table[feature][cfg_set] 
                if settings_map[setting] == '1':       
                    new_lines.append(f"#define {feature} 1\n") 
                    continue
        new_lines.append(line)
    with open("config.h", 'w') as f:
        f.writelines(new_lines)
    os.chdir(f"{cwd}")
    print(f"kconfig features:")
    for feature in kconfig_features:
        print(f"    feature: {feature}")
    return kconfig_features 

def get_busybox_kconfig_features(config_table, cfg_set=0):
    settings_map = {'True' : '1', 'False': '0', 'any': ''}
    cwd = os.getcwd()
    os.chdir(f"{cwd}/{busybox_version}")
    lines = getFileLines(".config")
    os.system("cp .config .config.old")
    new_lines = []
    kconfig_features = []
    for line in lines:
        if "CONFIG_" in line:
            if "#" in line and "is not set" in line:
                feature = line.replace("#", "")
                feature = feature.replace("is not set", "")
                feature = feature.strip()
                feature_in_code = feature.replace("CONFIG", "ENABLE")
                if feature_in_code in config_table:  
                    kconfig_features.append(feature_in_code)
                    setting = config_table[feature_in_code][cfg_set] 
                    if settings_map[setting] == '1':
                        new_lines.append(f"{feature}=y\n")
                        continue     
            elif "=y" in line:
                feature = line.replace("=y", "")
                feature = feature.strip()
                feature_in_code = feature.replace("CONFIG", "ENABLE")
                if feature_in_code in config_table:    
                    kconfig_features.append(feature_in_code)
                    setting = config_table[feature_in_code][cfg_set] 
                    if settings_map[setting] == '0':
                        new_lines.append(f"# {feature} is not set\n")
                        continue             
        new_lines.append(line)
    with open(".config", 'w') as f:
        f.writelines(new_lines)
    os.chdir(f"{cwd}")
    print(f"kconfig features:")
    for feature in kconfig_features:
        setting = config_table[feature][cfg_set]
        print(f"    feature: {feature}: setting {setting}")

    return kconfig_features 

def findKnownFeaturesInLine(features, line):
    feature_count = 0
    for feature in features:
        if feature in line:
            index = line.find(feature)
            end = index + len(feature)
            if end >= len(line) or (not re.search('[a-zA-Z0-9_]', line[end])):
                feature_count += 1
    return feature_count


def checkNestedIf(file_lines, line_n, feature_count, pc, features):
    line = file_lines[line_n]
    new_pc = pc
    if '#' in line and 'if' in line and 'endif' not in line:
        current_line_feature_count = findKnownFeaturesInLine(features, line)
        # already transform
        if current_line_feature_count == 0:
            return

        operator_count = 0
        end = len(new_pc)
        while operator_count < feature_count:
            or_index = new_pc.rfind('||', 0, end)
            and_index = new_pc.rfind('&&', 0, end)
            end = max(or_index, and_index)
            if end == -1:
                return
            operator_count += 1
        if 'elif' in line:
            file_lines[line_n] = "#elif " + new_pc[:end] + '\n'
        else:    
            file_lines[line_n] = "#if " + new_pc[:end] + '\n'
            checkNestedIf(file_lines, line_n-1, current_line_feature_count, new_pc[:end], features)

def transform_file(pc, internal_features, project):
    for file in pc.var_file_pc:
        print(f"transform file: {file}")
        command = f"cp {file} {file}.original"
        os.system(command)
        file_lines = getFileLines(file)
        for _pc in pc.var_file_pc[file]:
            features = getFeatures(_pc)
            new_pc = getPCEval(_pc, internal_features, project)
            if _pc != new_pc:
                line_numbers = []
                previous_n = -2
                for loc in pc.presence_condition_dict[_pc]:
                    if file in loc:
                        element = loc.split(':')
                        line_n = int(element[1].strip())
                        if line_n != previous_n + 1:
                            # line number starts at 0
                            line_numbers.append(line_n-2)
                        previous_n = line_n 
                for line_n in line_numbers:
                    cont = False
                    if '\\' in file_lines[line_n]:
                        cont = True
                    if '#elif' in file_lines[line_n] or ('# ' in file_lines[line_n] and 'elif' in file_lines[line_n]):
                        file_lines[line_n] = "#elif " + new_pc + '\n'
                    elif '#if' in file_lines[line_n] or ('# ' in file_lines[line_n] and 'if' in file_lines[line_n] and 'endif' not in file_lines[line_n]):
                        # find number of features in current line
                        feature_count = findKnownFeaturesInLine(features, file_lines[line_n])
                        file_lines[line_n] = "#if " + new_pc + '\n'
                        checkNestedIf(file_lines, line_n-1, feature_count, new_pc, features)
                    
                    if cont:
                        n = line_n + 1
                        while '\\' in file_lines[n]:
                            file_lines[n] = '\n'
                            n += 1
                        file_lines[n] = '\n'
        with open(file, 'w') as f:
            f.writelines(file_lines)
        command = f"cp {file} {file}.transform"
        os.system(command)

def main(rtwFile, mapFile, path, file, filter, project):
    pc = PresenceCondition(path, file, filter)
    if project == "cfs":
        pc.transform_file()
    start = time.time()
    if project == "ua_app":
        from PCLocator import extract_presence_conditions
        cur_time = time.time()
        supported_features = []
        for file in mapFile:
            with open(file, "r") as f:
                lines = f.readlines()
                for line in lines:
                    items = line.split()
                    if len(items) == 2:
                        supported_features.append(items[1].strip())
        print(f"supported_features: {supported_features}")
        print(f"Variability source code:")
        pc.src_list = getFileLines(pc.src_list_file)
        for file in pc.src_list:
            input_file = file.strip()
            ext = ".py"
            output_file = file.strip().replace(ext, f"{ext}.txt")
            print(f"   {input_file}")
            with open(input_file, "r") as f:
                code = f.read()
                extract_presence_conditions(code, supported_features, output_file)
        find_pc_time = round(time.time() - cur_time, 2)
        print(f"Total time for running PCLocator: {find_pc_time} seconds")
    else:
        # run ifnames to identify cpp files that support variability
        print("\nRunning ifnames tool to find c/cpp files that support variability. Please wait...")
        pc.runIfNames()
        # save variability features and files
        pc.saveVarFeaturesAndFiles()
        find_var_src_code_time = round(time.time() - start, 2)
        print(f"Total time for finding cpp files and variability features: {find_var_src_code_time} seconds")
        cur_time = time.time()
        # run PCLocator to identify presence conditions in variability code
        print("\nRunning PCLocator tool to identify presence conditions from variability source code. Please wait...")
        pc.runPCLocator()
        find_pc_time = round(time.time() - cur_time, 2)
        print(f"Total time for running PCLocator: {find_pc_time} seconds")
    cur_time = time.time()
    print("\nGenerating feature model. Please wait...")
    rtw = RTW(rtwFile, mapFile)
    #rtw.showRTWConstraints()
    #rtw.showSATFormula()
    print(f"Total time for feature model generation: {(time.time() - cur_time):.2f} seconds")
    cur_time = time.time()
    print("\nAnalyzing presence conditions. Please wait...")
    pc.findPresenceConditions()
    pc.reverseFeatureMap(rtw.code2feature_map)
    pc.discardNumericals()
    pc.showPresenceConditionsStat()
    pc.getAssignments()
    #pc.showAssignmentsWeight()
    pc.findFeaturesNotInFeatureModel()
    pc.findFeaturesInFeatureModel()
    if project == "ua_app":
        print("Removing files: ")
        # for file in pc.src_list:
        #     file = file.strip()
        #     ext = ".py"
        #     rm_file = file.strip().replace(ext, f"{ext}.txt")
        #     print(f"   {rm_file}")
        #     command = f"rm {rm_file}"
        #         os.system(command)        
    else:
        pc.cleanup()
    cur_time = time.time()
    sat_solver = SATSolver(rtw, pc, project=project)
    sat_solver.evalPresenceCondition(pc.assignment_list_weight, pc.assignment2presence_cond)
    pc_identify_analysis_time = round(time.time() - cur_time, 2)
    print(f"Total time for presence condition identification and analysis: {pc_identify_analysis_time} seconds")
    sat_solver.getMinConfigSet()
    rtw.showFeaturesNotInCode(sat_solver.feature_not_in_code, pc.stat)
    print("\nFinding min configuration sets. Please wait...")
    sat_solver.printConfigTable(rtw.code2feature_map, pc.stat)
    find_min_set_time = round(time.time() - cur_time, 2)
    print(f"\nTotal time for min configuration sets finding: {find_min_set_time} seconds")
    print(f"\nTotal time for variability analysis: {(time.time() - start):.2f} seconds")
    pc.stat.printStat(project)
    exit()
    print(f"##########################")
    print(f"Performance Analysis:")
    print(f"  find var src code: {find_var_src_code_time} s")
    print(f"  find presence condition and analysis: {find_pc_time + pc_identify_analysis_time} s")
    print(f"  find min set time: {find_min_set_time} s")
    print(f"##########################")
    with open(f"var_perf_{project}.csv", "a") as f:
    	f.write(f"{find_var_src_code_time}, {find_pc_time + pc_identify_analysis_time}, {find_min_set_time}\n")

    if project == "axtls":
        for cfg in range(len(sat_solver.configSet)):
            if cfg == 1:
                os.system("cp axtls_inject/tls1.c axtls-code/ssl/.")
            print(f"#################################################################################")
            print(f"Build configuration {cfg}")
            print(f"#################################################################################") 
            kconfig_features = get_axtls_kconfig_features(sat_solver.config_table, cfg_set=cfg)
            internal_features = get_internal_features(kconfig_features, sat_solver.config_table, cfg_set=cfg)
            transform_file(pc, internal_features, project)
            cwd = os.getcwd()
            os.chdir(f"{cwd}/axtls-code/")
            os.system("make")
            os.chdir(f"{cwd}")
            restore_file(pc.var_file_pc)
            print()
            if cfg < 2:
                print(f"#################################################################################")
                print(f"Re-build configuration {cfg}")
                print(f"#################################################################################") 
                os.system("cp axtls_fix/tls1.c axtls-code/ssl/.")
                kconfig_features = get_axtls_kconfig_features(sat_solver.config_table, cfg_set=cfg)
                internal_features = get_internal_features(kconfig_features, sat_solver.config_table, cfg_set=cfg)
                transform_file(pc, internal_features, project)
                os.chdir(f"{cwd}/axtls-code/")
                os.system("make")
                os.chdir(f"{cwd}")
                restore_file(pc.var_file_pc)
                print()
    elif "busybox" in project:
        for cfg in range(len(sat_solver.configSet)):
            print(f"#################################################################################")
            print(f"Build configuration {cfg}")
            print(f"#################################################################################") 
            kconfig_features = get_busybox_kconfig_features(sat_solver.config_table, cfg_set=cfg)
            internal_features = get_internal_features(kconfig_features, sat_solver.config_table, cfg_set=cfg)
            transform_file(pc, internal_features, project)
            cwd = os.getcwd()
            os.chdir(f"{cwd}/{busybox_version}/")
            os.system("make clean")
            os.system("make")
            os.chdir(f"{cwd}")
            restore_file(pc.var_file_pc)
            print()
            
if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Find Min Configuration Set for Max Line Coverage')
    parser.add_argument('--rtw_file', metavar='RTW input file', required=True, type=str, nargs='+', help='RTW input file name')
    parser.add_argument('--feature_map', metavar='feature map file', type=str, nargs='+', help='Feature to code mapping file')
    parser.add_argument('--path', metavar='path to file list for cpp files', required=True, help='path to file list for cpp files')
    parser.add_argument('--file', metavar='file name for list of cpp files', required=True, help='file list for cpp files')
    parser.add_argument('--filter', metavar='file list to filter', required=True, help='file list to filter')
    parser.add_argument('--project', metavar='project for analysis', type=str, required=True, help='project for analysis')
    args = parser.parse_args()
    main(rtwFile=args.rtw_file, mapFile=args.feature_map, path=args.path, file=args.file, filter=args.filter, project=args.project)
