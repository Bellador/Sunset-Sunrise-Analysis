# import dependencies
import time
import math
import pickle
import numpy as np
import pandas as pd
import sklearn.metrics
from pathlib import Path
from collections import Counter
from multiprocessing import Pool, cpu_count

'''
ANACONDA ENV: geoenv
PROCESSING STEPS (do everything for flickr sunset first - testing)
1. compare countries based on cosine similarity (build term vectors) of sunset / sunrise flickr, treat phenomena seperatly
1.1 link flickr_sunset to flickr_spatialref to get country code
1.2 group flickr_sunset by country code
1.3 calculate cosine similarity for flickr_sunset between countries
1.n calculate userdays per country
'''
# define if term frequency is calculated using all available cores
MULTIPROCESSING = True
# define which phenomenon is analysed
MODE = 'SUNSET' #OR SUNRISE
SOURCE = 'FLICKR' # OR INSTAGRAM OR ALL
# min. amount of unique userposts a country must have to be included in the processing
THRESHOLD = 25
# define search col where the flickr terms are found
term_col = 'user_terms'

if SOURCE == 'FLICKR':
    if MODE == 'SUNSET':
        # actual sunset/sunrise data. columns: userday, userday_terms, userday_season_id (Multiple/Ambiguous 0, Northern spring 1, Northern summer 2, Northern fall 3, Northern winter 4, Southern spring -1, Southern summer -2, Southern fall -3, Southern winter -4
        DATA_PATH = Path("./Semantic_analysis/2021-01-28_country_userterms/flickr_sunset_terms_user_country.csv") # CHANGE HERE IF NECESSARY
        # OUTPUT store path
        COSINE_SIMILARITY_STORE_PATH = Path("./Semantic_analysis/20210204_FLICKR_SUNSET_random_country_cosine_similarity.csv") # CHANGE HERE IF NECESSARY
        # STORE PATH FOR INTERMEDIATE PRODUCT - CALCULATED TERMS PER COUNTRY FLICKR POSTS (country_term_dict)
        COUNTRY_TERM_DICT_STORE_PATH = Path("./Semantic_analysis/20210204_FLICKR_SUNSET_country_term_dict.pickle")

    elif MODE == 'SUNRISE':
        # actual sunset/sunrise data. columns: userday, userday_terms, userday_season_id (Multiple/Ambiguous 0, Northern spring 1, Northern summer 2, Northern fall 3, Northern winter 4, Southern spring -1, Southern summer -2, Southern fall -3, Southern winter -4
        DATA_PATH = Path("./Semantic_analysis/Flickr_userday_terms_raw/flickr_sunrise_terms_geotagged_grouped.csv")
        # OUTPUT store path
        COSINE_SIMILARITY_STORE_PATH = Path("./Semantic_analysis/20210202_FLICKR_SUNRISE_country_cosine_similarity.csv")
        # STORE PATH FOR INTERMEDIATE PRODUCT - CALCULATED TERMS PER COUNTRY FLICKR POSTS (country_term_dict)
        COUNTRY_TERM_DICT_STORE_PATH = Path("./Semantic_analysis/20210202_FLICKR_SUNRISE_country_term_dict.pickle")

elif SOURCE == 'INSTAGRAM':
    if MODE == 'SUNSET':
        # spatial reference to unique userday hashaes. columns: userday, xbin, ybin, su_a3 (country code)
        # LOCATIONREF_PATH = Path("./Semantic_analysis/Flickr_userday_location_ref/flickr_sunset_userday_gridloc.csv")
        # actual sunset/sunrise data. columns: userday, userday_terms, userday_season_id (Multiple/Ambiguous 0, Northern spring 1, Northern summer 2, Northern fall 3, Northern winter 4, Southern spring -1, Southern summer -2, Southern fall -3, Southern winter -4
        DATA_PATH = Path("./Semantic_analysis/2021-01-28_country_userterms/instagram_sunset_terms_user_country.csv")  # CHANGE HERE IF NECESSARY
        # OUTPUT store path
        COSINE_SIMILARITY_STORE_PATH = Path("./Semantic_analysis/20210204_INSTAGRAM_SUNSET_random_country_cosine_similarity.csv")  # CHANGE HERE IF NECESSARY
        # STORE PATH FOR INTERMEDIATE PRODUCT - CALCULATED TERMS PER COUNTRY FLICKR POSTS (country_term_dict)
        COUNTRY_TERM_DICT_STORE_PATH = Path("./Semantic_analysis/20210204_INSTAGRAM_SUNRSET_country_term_dict.pickle")

    elif MODE == 'SUNRISE':
        # spatial reference to unique userday hashaes. columns: userday, xbin, ybin, su_a3 (country code)
        # LOCATIONREF_PATH = Path("./Semantic_analysis/Flickr_userday_location_ref/flickr_sunrise_userday_gridloc.csv")
        # actual sunset/sunrise data. columns: userday, userday_terms, userday_season_id (Multiple/Ambiguous 0, Northern spring 1, Northern summer 2, Northern fall 3, Northern winter 4, Southern spring -1, Southern summer -2, Southern fall -3, Southern winter -4
        DATA_PATH = Path("./Semantic_analysis/2021-01-28_country_userterms/instagram_sunrise_terms_user_country.csv")
        # OUTPUT store path
        COSINE_SIMILARITY_STORE_PATH = Path("./Semantic_analysis/20210204_INSTAGRAM_SUNRISE_country_cosine_similarity.csv")
        # STORE PATH FOR INTERMEDIATE PRODUCT - CALCULATED TERMS PER COUNTRY FLICKR POSTS (country_term_dict)
        COUNTRY_TERM_DICT_STORE_PATH = Path("./Semantic_analysis/20210204_INSTAGRAM_SUNRISE_country_term_dict.pickle")

def calc_vocabulary():
    '''
    PROCESSING STEP 1
    '''
    # 1.1
    # load data, use 'converters={'column_name': eval}' to evaluate the columns to their designated object. Because dataframe
    # was saved as CSV, therefore text, a stored list or series must be converted back otherwise it will appear as string
    data_w_locationref_df = pd.read_csv(DATA_PATH)
    # 1.2 retrieve unique country codes for iteration
    country_codes = data_w_locationref_df['su_a3'].unique()
    # create dict that holds the terms for all posts inside one country based on which cosine similarity will be calcualted
    country_term_dict = {}
    print(f'column dtypes: {data_w_locationref_df.dtypes}')
    print('preprosses userday terms...')
    data_w_locationref_df[term_col] = data_w_locationref_df[term_col].apply(lambda x: x.strip('{}'))
    print('build entire corpus vocabulary (set)...')
    corpus_vocabulary_str = ','.join(data_w_locationref_df[term_col])
    # convert to set for unique values and then back to chararray for access the index function later on
    corpus_unique_vocabulary_array = list(set(corpus_vocabulary_str.split(',')))
    corpus_unique_voc_array_len = len(corpus_unique_vocabulary_array)
    print(f'len corpus vocabulary (set): {corpus_unique_voc_array_len}')
    print(f'create dict of corpus vocabulary that associates the term index in the array with the term itself...')
    corpus_vocabulary_index_dict = {}
    start = time.time()
    for index, term in enumerate(corpus_unique_vocabulary_array):
        corpus_vocabulary_index_dict[term] = index
    end = time.time()
    print(f'time diff: {round(end - start)}s')
    print(f'build vocabulary for all countries with min. {THRESHOLD} unique userposts...')
    for country_index, country_code in enumerate(country_codes):
        country_df = data_w_locationref_df[data_w_locationref_df['su_a3'] == country_code]
        # check if len of subdf: country_df is higher than or equal the threhold
        if len(country_df.index.values) >= THRESHOLD:
            # # 1.n calculate unique userdays per country and display
            print(f'Unique userdays: {country_code}    :      {len(country_df.index.values)}')
            # build country vocabulary
            country_vocabulary_str = ','.join(country_df[term_col])
            country_vocabulary_list = country_vocabulary_str.split(',')
            # create Counter object for country terms, therefore the count number of each term is acquired
            country_vocabulary_counter = Counter(country_vocabulary_list)
            # store in dictionary
            country_term_dict[country_code] = country_vocabulary_counter
        else:
            # excluded
            print(f'Unique userdays: {country_code}    :      {len(country_df.index.values)} - EXCLUDED')

    # create updated country_codes with the ones over the THRESHOLD
    country_codes = list(country_term_dict.keys())
    # create dataframe which holds cosine similarities between countries
    countries_cosine_similarity_df = pd.DataFrame(index=country_codes, columns=country_codes)

    return country_term_dict, corpus_unique_vocabulary_array, corpus_unique_voc_array_len, corpus_vocabulary_index_dict, country_codes, countries_cosine_similarity_df


def calc_term_vector(country_term_dict, corpus_vocabulary_set, corpus_vocabulary_set_len, corpus_vocabulary_index_dict, country_codes, tracker=1):
    # create dict that holds the terms_VECTORES for all post
    country_vector_dict = {}
    # create the vector of all posts based on the overall corpus vocabulary
    print('\ncalculating term vectors...')
    for index, country_code in enumerate(country_codes, 1):
        print(f'Process {tracker}: {index} of {len(country_codes)}\n')
        country_terms_counter = country_term_dict[country_code]
        # create a blueprint country_vector with the length of the entire corpus vocabulary and default value of 0
        country_vector = [0] * corpus_vocabulary_set_len
        # iterate over country term counter object
        country_terms_len = len(country_terms_counter.keys())
        for index2, (term, frequency) in enumerate(country_terms_counter.items()):
            print(f'\r{index2} of {country_terms_len}', end='')
            # find index of term in entire vocabulary corpus
            corpus_vocabulary_term_index = corpus_vocabulary_index_dict[term]
            #corpus_vocabulary_term_index = corpus_vocabulary_set.index(term) # its actually not a set, but a list of unique items
            # replace 0 at given index with frequency of Counter object for given term
            country_vector[corpus_vocabulary_term_index] = frequency
        # convert to numpy array
        country_vector = np.array(country_vector)
        # reshape the vector to fit the sklearn cosine similarity function
        country_vector = country_vector.reshape(1, -1)
        country_vector_dict[country_code] = country_vector
    return country_vector_dict

def calc_cosine_similarity(country_vector_dict, countries_cosine_similarity_df):
    # 1.3 calculate cosine similarity between countries by iterating over the country_term_dict and assigning it to the countries_cosine_similarity dataframe
    print('calculating cosine similarity between country term vectors')
    for index, country_code_1 in enumerate(country_codes, 1):
        print(f'progress: {index} of {len(country_codes)}')
        country_vector_1 = country_vector_dict[country_code_1]
        for country_code_2 in country_codes:
            if country_code_1 != country_code_2:
                country_vector_2 = country_vector_dict[country_code_2]
                cosine_similarity = sklearn.metrics.pairwise.cosine_similarity(country_vector_1, Y=country_vector_2, dense_output=True)
                # extract cosine similarity out of the lists in which it is contained
                try:
                    cosine_similarity = cosine_similarity[0][0]
                except Exception as e:
                    print(f'Cosine Similarity extraction fail: {e}')
            else:
                cosine_similarity = 1
            # add cosine similarity to dataframe
            countries_cosine_similarity_df.loc[country_code_1, country_code_2] = cosine_similarity
    # save cosine_similarity_df
    print(f'saving cosine similarities under: {COSINE_SIMILARITY_STORE_PATH}')
    countries_cosine_similarity_df.to_csv(COSINE_SIMILARITY_STORE_PATH)
    return countries_cosine_similarity_df


if __name__ == '__main__':
    # cosine_similarity dict is still empty here, was only initialised
    country_term_dict, corpus_vocabulary_set, corpus_vocabulary_set_len, corpus_vocabulary_index_dict, country_codes, countries_cosine_similarity_df = calc_vocabulary()
    # dump country_term_dict as pickl format
    try:
        with open(COUNTRY_TERM_DICT_STORE_PATH, 'wb') as handle:
            pickle.dump(country_term_dict, handle)
    except Exception as e:
        print(f'Error: {e}')
        print('Could not pickle country_term_dict...')
        print('Continuing...')
    if MULTIPROCESSING:
        print(f'starting process on {cpu_count()} cores...')
        # distribute work over cores based on country_code splits
        nr_country_codes_per_process = math.ceil(len(country_codes) / cpu_count())
        arguments = []
        # prepare arguments for processes
        for i in range(cpu_count()):
            # number to track process in print statements
            tracker = i + 1
            # if last process take the remaining rest
            if i == (cpu_count()-1):
                country_codes_process_share = country_codes[(i * nr_country_codes_per_process):]
            else:
                country_codes_process_share = country_codes[(i*nr_country_codes_per_process):((i+1)*nr_country_codes_per_process)]
            arguments.append((country_term_dict, corpus_vocabulary_set, corpus_vocabulary_set_len, corpus_vocabulary_index_dict, country_codes_process_share, tracker))
        # convert to tuple
        arguments = tuple(arguments)
        with Pool() as pool:
            country_vector_dict_list = pool.starmap(calc_term_vector, arguments)
        # merge dictionaries that were generated by the different processes
        country_vector_dict = {}
        for dict_ in country_vector_dict_list:
            country_vector_dict.update(dict_)
    # no multiprocessing
    else:
        country_vector_dict = calc_term_vector(country_term_dict, corpus_vocabulary_set, corpus_vocabulary_set_len, corpus_vocabulary_index_dict, country_codes)
    # compute the cosine similarity between all country specific term vectors
    countries_cosine_similarity_df = calc_cosine_similarity(country_vector_dict, countries_cosine_similarity_df)
    print('done.')