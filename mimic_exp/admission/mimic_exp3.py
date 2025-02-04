import sys
sys.path.append("/home/wanxinli/EHR-OT/")

from ast import literal_eval
# from common import *
from mimic_common import *
from multiprocess import Pool
import os
import random
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.decomposition import PCA
from sklearn.metrics import precision_score, recall_score, accuracy_score, f1_score
import time


output_dir = os.path.join(os.path.expanduser("~"), f"EHR-OT/outputs/mimic")
print(f"Will save outputs to {output_dir}")


""" 
Read in the original dataframe
"""
admid_diagnosis_df = pd.read_csv("../../outputs/mimic/ADMID_DIAGNOSIS_selected.csv", index_col=0, header=0, converters={'ICD codes': literal_eval})
print(admid_diagnosis_df)

""" 
Print number of patients for each category
"""
print("female label 0", admid_diagnosis_df.loc[(admid_diagnosis_df['label'] == 0) & (admid_diagnosis_df['gender'] == 'F')].shape[0])
print("female label 1", admid_diagnosis_df.loc[(admid_diagnosis_df['label'] == 1) & (admid_diagnosis_df['gender'] == 'F')].shape[0])
print("male label 0", admid_diagnosis_df.loc[(admid_diagnosis_df['label'] == 0) & (admid_diagnosis_df['gender'] == 'M')].shape[0])
print("male label 1", admid_diagnosis_df.loc[(admid_diagnosis_df['label'] == 1) & (admid_diagnosis_df['gender'] == 'M')].shape[0])


"""
Train deep patient model and generate representations for targets and sources
"""

def custom_train_reps(source_features, target_features, n_components, pca_explain=False):
    """ 
    Customized training algorithm for generating target representations and source representations

    :param bool pca_explain: print the explained variance of each components
    
    :returns: target representations, source representations
    """
    source_pca = PCA(n_components=n_components)
    source_reps = source_pca.fit_transform(source_features)

    target_pca = PCA(n_components=n_components)
    target_reps = target_pca.fit_transform(target_features)

    if pca_explain:
        source_exp_var = source_pca.explained_variance_ratio_
        source_cum_sum_var = np.cumsum(source_exp_var)
        target_exp_var = target_pca.explained_variance_ratio_
        target_cum_sum_var = np.cumsum(target_exp_var)
        print("Cummulative variance explained by the source PCA is:", source_cum_sum_var)
        print("Cummulative variance explained by the target PCA is:", target_cum_sum_var)

    return source_reps, target_reps


def multi_proc_parallel(score_path, n_components, label_code, custom_train_reps, \
        male_count, female_count, iteration=20, max_iter = None):
    """ 
    Code cannot be parallized when passing the dataframe (full_df) as a parameter
    Hence, cannot be put into mimic_common.py
    """
    
    p = Pool(10)

    # note: the following line cannnot be used for parallelization either
    # admid_diagnosis_df = pd.read_csv("../../outputs/mimic/ADMID_DIAGNOSIS.csv", index_col=0, header=0, converters={'ICD codes': literal_eval})

    def iteration_wrapper(iter):
        """ 
        Wrapper function for one iteration, returns result statistics, for parallel computing

        :param int iter: the current iteration
        """
        print(f"iteration: {iter}\n")
        cur_res = entire_proc_binary(n_components, "gender", 'M', 'F', label_code, admid_diagnosis_df, custom_train_reps, \
                                     male_count = male_count, female_count = female_count, transfer_score=True, max_iter=max_iter)

        
        return cur_res

    res = p.map(iteration_wrapper, np.arange(0, iteration, 1))
    res_df = pd.DataFrame(res, columns = ['source_accuracy', 'source_precision', 'source_recall', 'source_f1', \
                                          'target_accuracy', 'target_precision', 'target_recall', 'target_f1', \
                                            'trans_target_accuracy', 'trans_target_precision', 'trans_target_recall', 'trans_target_f1', \
                                            'transfer_score', 'w_dist'])
    res_df.to_csv(score_path, index=False, header=True)
    return res

""" 
Run the entire proc for all response (i.e., label_code) 
Responses are selected by select_codes.ipynb and saved in ../../outputs/mimic/selected_summary_mimic.csv
"""

n_components = 50
male_count = 120
female_count = 100
label_code_path = os.path.join(output_dir, "ADMID_DIAGNOSIS_selected.csv")
label_code_df = pd.read_csv(label_code_path, header=0, index_col=0, converters={'ICD codes': literal_eval})
label_codes = list(label_code_df['ICD codes'])
label_codes = list(set([item for sublist in label_codes for item in sublist]))
print("number of label_codes are:", len(label_codes))


# label_codes = label_codes[200:]
for label_code in label_codes:
    score_path = os.path.join(output_dir, f"exp3_{label_code}_score.csv")
    if os.path.exists(score_path):
        print(f"score for {label_code} has been computed")
        continue
    start_time = time.time()
    print(f"label code {label_code} started")
    multi_proc_parallel(score_path, n_components, label_code, custom_train_reps, \
            male_count, female_count, iteration=10)
    end_time = time.time()
    print(f"runtime for {label_code} is: {end_time-start_time}")



def multi_proc_parallel_default(score_path, n_components, label_code, custom_train_reps, \
        male_count, female_count, trans_metric, iteration=20):
    """ 
    Code cannot be parallized when passing the dataframe (full_df) as a parameter
    Hence, cannot be put into mimic_common.py

    :param str trans_metric: transporting metric
    """
    
    p = Pool(10)

    def iteration_wrapper(iter):
        """ 
        Wrapper function for one iteration, returns result statistics, for parallel computing

        :param int iter: the current iteration
        """
        print(f"iteration: {iter}\n")
        cur_res = entire_proc_binary(n_components, "gender", 'M', 'F', label_code, \
                    admid_diagnosis_df, custom_train_reps, model_func=linear_model.LogisticRegression, \
                    trans_metric=trans_metric, male_count = male_count, female_count = female_count)
        
        return cur_res

    res = p.map(iteration_wrapper, np.arange(0, iteration, 1))
    res_df = pd.DataFrame(res, columns = ['source_accuracy', 'source_precision', 'source_recall', 'source_f1', \
                                          'target_accuracy', 'target_precision', 'target_recall', 'target_f1', \
                                            'trans_target_accuracy', 'trans_target_precision', 'trans_target_recall', 'trans_target_f1'])
    res_df.to_csv(score_path, index=False, header=True)
    return res


label_codes = label_codes
print("label_codes are:", label_codes)
trans_metric = 'MMD' # MMD using sigmoid
for label_code in label_codes:
    score_path = os.path.join(output_dir, f"exp3_{label_code}_{trans_metric}_score.csv")
    print(f"score_path is: {score_path}")
    if os.path.exists(score_path):
        print(f"score for {label_code} has been computed")
        continue
    start_time = time.time()
    print(f"label code {label_code} started")
    multi_proc_parallel_default(score_path, n_components, label_code, custom_train_reps, \
            male_count, female_count, 'MMD', iteration=100)
    end_time = time.time()
    print(f"runtime for {label_code} is: {end_time-start_time}")