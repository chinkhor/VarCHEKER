# VarCHEKER - A Variability-based Static Analyzer for Python Applications

VarCHEKER analyzes variability requirements and Python source code to detect inconsistencies and generate test configurations for use in variability testing. User can setup to show the results through a real-time Grafana dashboard. Additionally, VarCHEKER generates feature model that can be inspected and visualized using FeatureIDE.

## Setup and Installation

1. Download [VarCHEKER-v1.0.0](https://github.com/chinkhor/VarCHEKER/releases/tag/v1.0.0)
2. Run `./scripts/setup.sh` at terminal to install dependencies

## Usage

1. Run VarCHEKER at terminal
```bash
./VarCHEKER.sh <requirement csv file> <source code dir path>
```
e.g.
```bash
./VarCHEKER.sh sample/sample_requirements.csv sample/sample_app
```
note: 
* sample requirements (`sample/sample_requirements.csv`) and sample Python application (`sample/sample_app/sample.py`) are provided for demonstration

2. VarCHEKER results will be printed in terminal console
3. VarCHEKER will generate the following artifacts:
    - `feature_model/FeatureModel.xml`
    - `reports/stat.csv`
    - `reports/presence_condition.csv`
    - `reports/min_set.csv `
    - `reports/required_features_not_in_code.csv`
    - `reports/code_features_not_in_requirements.csv`
    - `reports/inconsistencies.csv`

## How to create formatted variability requirements (CSV file)

1. Start with requirements template provided in `template/RTW_template.csv`
2. The user requires to enter the following five fields for each variability requirement (CSV format)
![alt text](image-2.png)
    - Requirement ID: unique ID
    - Valid: control the requirement inclusion/exclusion 
        - 1 : valid
        - 0 : invalid 
    - Parent Feature: feature name for parent feature
    - Children Feature(s): feature name for one or more children features
    - Rule: relationship rules for Parent-Children and Cross-Tree Constraints (see figure below)
![alt text](image.png)
3. Examples:
![alt text](image-5.png)
Features that are not directly configurable in the source code are prefixed with `abstract_` to improve grouping and readability. We refer to these as `abstract features`.
    - ID-1: the feature `car` is root, rule is R1. 
        - The feature `car` is an abstract feature, and is represented with the `abstract_` prefix as `abstract_car`.
    - ID-2: the feature `abstract_car` shall have `transmission`. `transmission` is a mandatory child feature of `abstract_car`, rule is R2. 
        - The feature `transmission` is also an abstract feature, is represented with `abstract_transmission`. 
    - ID-2.1: the feature `abstract_transmission` has two choices (i.e., children): `automatic` or `manual`, but only one child can be selected, rule is R4.
        - The enumerated feature `abstract_transmission` has two choices: `automatic` or `manual`. We transform this enumerated feature into two Boolean concrete features: `transmission==automatic`, `transmission==manual`. These represent configurable options in the source code.
    - ID-3: the feature `abstract_car` may have `clutch`. `clutch` is optional child feature of `abstract_car`, rule is R3. 
        - The feature `clutch` is concrete feature, i.e., directly configurable in the source code.
    - ID-4: feature `clutch` requires `transmission==manual`. As `clutch` and `transmission==manual` are both children of `abstract_car`, their relationship is represented as a cross-tree constraint using rule R7.

## Visualize the VarCHEKER results using Grafana Dashboard

1. Setup public repo (e.g. github) 
2. Copy six csv files from `reports\*.csv` to the repo
3. Modify the repo urls for all csv files in  `template/VarCHEKER-dashboard-template.json` 
4. Create Grafana account
5. Create new Dashboard by importing dashboard from `template/VarCHEKER-dashboard-template.json`
6. A sample dashboard snapshot link is available in `dashboard/README.md` for reference 

## Visualize the feature model using FeatureIDE

1. Install Eclipse
2. Go to Eclipse Marketplace, find and install FeatureIDE
3. Open Perspective and select FeatureIDE
4. Create new FeatureIDE project
5. Right click model.xml of new FeatureIDE project, select FeatureIDE and import Feature Model
6. Import model from `feature_model/FeatureModel.xml`

## Demo

Demo video is available here
