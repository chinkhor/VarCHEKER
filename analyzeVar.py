from RTW import RTW
from PresenceCondition import PresenceCondition
from PCLocator import extract_presence_conditions
from SATSolver import SATSolver
import time
import os
from PresenceCondition import getFileLines
import subprocess
import re


def get_feature(var_name, operator_map):
    # filter operator (if any) from var_name 
    for op_key in operator_map:
        if f"_{op_key}_" in var_name:
            lhs, rhs = var_name.split(f"_{op_key}_", 1)
            return lhs
    # filter out abstract feature, i.e. with abstract prefix
    if "abstract" in var_name:
        return ""
    return var_name

def main(rtwFile, mapFile, path, file, filter, project):
    operator_map = ['eq_to', 'not_eq', 'gr_th', 'le_th', 'gr_eq', 'le_eq']
    pc = PresenceCondition(path, file, filter)
    start = time.time()
    cur_time = time.time()
    supported_features = []
    for file in mapFile:
        with open(file, "r") as f:
            lines = f.readlines()
            for line in lines:
                items = line.split()
                if len(items) == 2:
                    feature = get_feature(items[1].strip(), operator_map)
                    if feature != "" and feature not in supported_features:
                        supported_features.append(feature)
    #print(f"supported_features: {supported_features}")
    #print(f"Variability source code:")
    pc.src_list = getFileLines(pc.src_list_file)
    for file in pc.src_list:
        input_file = file.strip()
        ext = ".py"
        output_file = file.strip().replace(ext, f"{ext}.txt")
        print(f"   {input_file}")
        with open(input_file, "r") as f:
            code = f.read()
            extract_presence_conditions(code, supported_features, output_file)
    print(f"Total files: {len(pc.src_list)}")
    find_pc_time = round(time.time() - cur_time, 2)
    print(f"Total time for running PCLocator: {find_pc_time} seconds")
    cur_time = time.time()
    print("\nGenerating feature model. Please wait...")
    rtw = RTW(rtwFile, mapFile)
    #rtw.showRTWTable()
    print(f"Total time for feature model generation: {(time.time() - cur_time):.2f} seconds")
    cur_time = time.time()
    #rtw.showSATFormula()
    print("\nAnalyzing presence conditions. Please wait...")
    pc.findPresenceConditions()
    pc.reverseFeatureMap(rtw.code2feature_map)
    #pc.showFeatureModelMap()
    #rtw.showFeatureMap()
    #pc.discardNumericals()
    pc.showPresenceConditionsStat()
    
    pc.getAssignments()
    #pc.showAssignmentsWeight()
 
    pc.findFeaturesNotInFeatureModel()
    pc.findFeaturesInFeatureModel()
    print("Removing files: ")
    # for file in pc.src_list:
    #     file = file.strip()
    #     ext = ".py"
    #     rm_file = file.strip().replace(ext, f"{ext}.txt")
    #     print(f"   {rm_file}")
    #     command = f"rm {rm_file}"
    #         os.system(command)  
         
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
