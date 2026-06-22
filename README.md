# VarCHEKER - A Variability-based Static Analyzer for Python Applications

VarCHEKER analyzes variability requirements and Python source code to detect inconsistencies and generate test configurations for use in variability testing. The results are reported through a real-time Grafana dashboard. Additionally, VarCHEKER generates feature model that can be inspected and visualized using FeatureIDE.

## Setup and Installation

1. Download [VarCHEKER-v1.0.0](https://github.com/chinkhor/VarCHEKER/releases/tag/v1.0.0)
2. Run `./scripts/setup.sh` to install dependencies

## Usage

1. Run VarCHEKER 
```bash
./VarCHEKER.sh <requirement csv file> <source code dir path>
```
e.g. `./VarCHEKER.sh sample_app/RTW_sample.csv sample_app/`

2. VarCHEKER will print results in console
3. VarCHEKER will generate artifacts:
    - `feature_model/FeatureModel.xml`
    - `reports/stat.csv`
    - `reports/presence_condition.csv`
    - `reports/min_set.csv `
    - `reports/required_features_not_in_code.csv`
    - `reports/code_features_not_in_requirements.csv`
    - `reports/inconsistencies.csv`

## Visualize the feature model using FeatureIDE

1. Install Eclipse with FeatureIDE plugin
2. Create new FeatureIDE project
3. Import model from `feature_model/FeatureModel.xml`

## Visualize the VarCHEKER results using Grafana Dashboard

1. Setup public repo (e.g. github) to store the 6 csv files from `reports\*.csv`
2. Modify the repo urls for all csv files in  `template\VarCHEKER-dashboard-template.json` 
3. Create Grafana account
4. Create new Dashboard by importing dashboard from `template\VarCHEKER-dashboard-template.json`
5. VarCHEKER results will be displayed over 6 panels 

## How to create formatted variability requirements (CSV file)

1. Start with template provided in `template/RTW_template.csv`
2. Refer to the paper's Variability Model Creator section for technical details.
3. Refer to youtube video below for how-to

## Demo

Demo video is available here
