import json
import requests
import pandas as pd

base = "https://www.sefaria.org.il"
def search(s):
    url = base + "/api/search-wrapper"
    params = { 
        "query": s,
        "type": "text",
        "field": "exact",

    }

    r = requests.post(url, json=params)
    r = r.json()
    return r

def search_v1(s, results=0):
    url = base + "/api/search/text/_search"
    # q = {
    #     "from":0,  
    #     "size":100,  
    #     "highlight":{
    #         "pre_tags":[  
    #             "<b>"
    #         ],
    #         "post_tags":[
    #             "</b>"
    #         ],
    #         "fields":{  
    #             "exact":{
    #                 "fragment_size":200
    #             }
    #         }
    #     },

    #     "query":{
    #         "match_phrase":{
    #             "exact":{
    #                 "query":s
    #             }
    #         }
    #     }
    # }

    pos = 0

    q = {
        "from": pos,  
        "size": 1000,  
        "highlight": {
            "pre_tags": ["<b>"],
            "post_tags": ["</b>"],
            "fields": {  
                "exact": {
                    "fragment_size": 200
                }
            }
        },
        "query": {
            "wildcard": {
                "exact": {
                    "value": f"{s}"
                }
            }
        }
    }

    df = pd.DataFrame(columns=["s", "highlight", "text_url"])
    
    while True:
        r = requests.post(url, json=q)
        r = r.json()
        hits = r["hits"]["hits"]
        # data frame with columns: s, highlight, text_url
        for h in hits:
            ref = h["_source"]['ref']
            #replase space with underscore
            text_url = base + '/' + ref.replace(" ", "_") + "?lang=he"
            highlight = h["highlight"]["exact"][0]
            df_tmp = pd.DataFrame({"s":[s], "highlight":[highlight], "text_url":[text_url]})
            df = pd.concat([df, df_tmp], ignore_index=True)
        pos += 1000
        q["from"] = pos

        if results > 0 and len(df) > results:
            break

        if len(hits) < 1000:
            break

    return df


def search_v1_regx(s, results=0):
    url = base + "/api/search/text/_search"
    # q = {
    #     "from":0,  
    #     "size":100,  
    #     "highlight":{
    #         "pre_tags":[  
    #             "<b>"
    #         ],
    #         "post_tags":[
    #             "</b>"
    #         ],
    #         "fields":{  
    #             "exact":{
    #                 "fragment_size":200
    #             }
    #         }
    #     },

    #     "query":{
    #         "match_phrase":{
    #             "exact":{
    #                 "query":s
    #             }
    #         }
    #     }
    # }

    pos = 0

    q = {
        "from": pos,  
        "size": 1000,  
        "highlight": {
            "pre_tags": ["<b>"],
            "post_tags": ["</b>"],
            "fields": {  
                "exact": {
                    "fragment_size": 200
                }
            }
        },
        "query": {
            "regexp": {
                    "exact": {
                        "value": f"{s}"
                    } 
            }
        }
    }

    df = pd.DataFrame(columns=["s", "highlight", "text_url"])
    
    while True:
        r = requests.post(url, json=q)
        r = r.json()
        hits = r["hits"]["hits"]
        # data frame with columns: s, highlight, text_url
        for h in hits:
            ref = h["_source"]['ref']
            #replase space with underscore
            text_url = base + '/' + ref.replace(" ", "_") + "?lang=he"
            highlight = h["highlight"]["exact"][0]
            df_tmp = pd.DataFrame({"s":[s], "highlight":[highlight], "text_url":[text_url]})
            df = pd.concat([df, df_tmp], ignore_index=True)
        pos += 1000
        q["from"] = pos

        if results > 0 and len(df) > results:
            break

        if len(hits) < 1000:
            break

    return df


def get_text(ref):
    url = base + "/api/texts/" + ref
    r = requests.get(url)
    r = r.json()
    return r

def end_letters_errors():
    end_letters = ["ך", "ם", "ן", "ף", "ץ"]
    reg_letters = "אבגדהוזחטיכלמנסעפצקרשת"

    df = pd.DataFrame(columns=["s", "highlight", "text_url"])

    for letter in end_letters:
        for reg_letter in reg_letters:

            s =  '*' + letter + reg_letter + '*'
            r = search_v1(s)
            # append r to datafarme
            l = len(r)
            print(f'search for {s} returned {l} results')
            df = pd.concat([df, r], ignore_index=True)

    return df
            


i = search_v1_regx("* d.*", 100)

r = end_letters_errors()
r.to_csv("search1.csv", index=False)