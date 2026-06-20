from RTW import RTW
from PresenceCondition import PresenceCondition, getFileLines
from PCExtractor import extract_presence_conditions
from SATSolver import SATSolver
import time
import os
import subprocess
import re


def main(rtwFile, file):
    start_time = time.time()
    print("\nGenerating feature model. Please wait...")
    rtw = RTW(rtwFile)
    # rtw.showRTWTable()
    # rtw.showSATFormula()
    # rtw.showSupportedFeatures()
    # rtw.showFeatureAssignmentChoice()
    print(f"Total time for feature model generation: {(time.time() - start_time):.2f} seconds")

    pc = PresenceCondition(file, rtw.support_features)
    cur_time = time.time()
    pc.src_list = getFileLines(pc.src_list_file)
    for file in pc.src_list:
        input_file = file.strip()
        ext = ".py"
        output_file = file.strip().replace(ext, f"{ext}.txt")
        #print(f"   {input_file}")
        with open(input_file, "r") as f:
            code = f.read()
            extract_presence_conditions(code, rtw.support_features, output_file)
    print(f"Total files: {len(pc.src_list)}")
    find_pc_time = round(time.time() - cur_time, 2)
    print(f"Total time for running PCExtractor: {find_pc_time} seconds")
    cur_time = time.time()
    print("\nAnalyzing presence conditions. Please wait...")
    pc.findPresenceConditions()
    pc.showPresenceConditionsStat()
    
    pc.getAssignments()
    #pc.showAssignmentsWeight()
 
    pc.findFeaturesNotInFeatureModel()
    pc.findFeaturesInFeatureModel()
    rtw.showFeaturesNotInCode(pc.features_dict, pc.stat)

    # remove the generated files for parsing
    for file in pc.src_list:
        file = file.strip()
        ext = ".py"
        rm_file = file.strip().replace(ext, f"{ext}.txt")
        command = f"rm {rm_file}"
        os.system(command)       
    cur_time = time.time()
    sat_solver = SATSolver(rtw, pc)
    sat_solver.evalPresenceCondition(pc.assignment_list_weight, pc.assignment2presence_cond)
    pc_identify_analysis_time = round(time.time() - cur_time, 2)
    print(f"Total time for presence condition identification and analysis: {pc_identify_analysis_time} seconds")
    
    sat_solver.getMinConfigSet()
    print("\nFinding min configuration sets. Please wait...")
    sat_solver.printConfigTable(rtw.support_features, pc.stat)
    find_min_set_time = round(time.time() - cur_time, 2)
    print(f"\nTotal time for min configuration sets finding: {find_min_set_time} seconds")
    print(f"\nTotal time for variability analysis: {(time.time() - start_time):.2f} seconds")
    pc.stat.printStat()
    
            
if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--rtw_file', metavar='Requirements CSV', required=True, type=str, nargs='+', help='Requirements CSV file name')    
    parser.add_argument('--file', metavar='file list', required=True, help='file list for .py files')
    args = parser.parse_args()
    main(rtwFile=args.rtw_file, file=args.file)
