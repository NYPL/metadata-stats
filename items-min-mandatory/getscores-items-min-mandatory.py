'''
Script to iterate through item-level records extracted from the NYPL Metadata Management System (MMS), assess completeness of
mandatory metadata elements, and assign pass/fail scores. Outputs a csv file with a set of record scores per row. Scores are assigned
for the following criteria:
title_1: Record has at least one title with text
title_2: Record has one title marked usage="primary"
title: Avg title score
typeOfResource: typeOfResource is present and matches an allowed value
genre_1: Record has at least one genre with text
genre_2: Genre has authority="*"
genre: Avg Genre score
date_1: Record has at least one numeric date
date_2: Record has W3CDTF encoded date
date_3: When more than one single date instance is present, there is no more than one instance of each date type.
date_4: If multiple date instances are present, none is a range.
date: Avg date score
identifier: Record has at least one identifier of type: "local_bnumber", "local_mss", or "local_tms"
location_1: Record has Repository information
location_2: Record has Division information
location_3: Record has Shelf Locator
location_4: Record has multiple location elements with consistent Division values
location_5: Record has all three division location types: "division", "division_short_name", "code"
location: Avg location score
total_min_mand: Min mand total score
'''

import modsqual
import json
import csv
import time
from __future__ import division
from collections import Counter

def score(bool, point=True, value=1):
    """assign points if bool value matches point argument value"""
    if bool == point:
        score = value
    else:
        score = 0
    return score

def exists(element):
    """top-level element exists"""
    s = score(element.exists)
    return s


def inList(element, list):
    """element value matches a value from a controlled vocabulary"""
    if element.exists == True:
        s = score(all(i in list for i in element.text()))
    else:
        s = 0
    return s

def xpathexists(match, min=1):
    """result from xpath match contains at least one element match"""
    try:
        s = score(len(match) >= min)
    except:
        s = 0
    return s

            
def xpathtextexists(match, min=1):
    """at least one element instance exists and values are longer than min (default = 1)"""
    #change path to text once you have modsqual fixed to return text values
    try:
        s = score(all(len(x.items()[0][1]['#text']) >= min for x in match))
    except:
        s = 0
    return s
        
def xpathexactlyone(match):
    """result from xpath match contains exactly one match"""
    try:
        s = score(len(match) == 1)
    except:
        s = 0
    return s

def xpathmax(match, max=1):
    """result from xpath is less or equal to max"""
    try:
        s = score(len(match) <= max)
    except:
        s = 0
    return s
        
def xpathvaluesmatch(match):
    """all results from xpath query match"""
    try:
        if len(match) > 0:
            s = score(all(x == match[0] for x in match))
        else:
            s = 0
    except:
        s = 0
    return s

def discretedatetypes(match):
    """scores if multiple dates have different date types"""
    try:
        counts = Counter()
        for c in match:
            counts[c.keys()[0]] += 1
        datetypes = dict(counts)
        if len(datetypes) > 0:
            s = score(all(v == 1 for x, v in datetypes.items()))
        else:
            s = 0
    except:
        s = 0
    return s

def multiplesingledates(modsdoc):
    """scores if multiple dates do not include ranges"""
    datecount = len(modsdoc.originInfo.match(xpath='./m:originInfo/m:dateCreated|./m:originInfo/m:dateIssued|./m:originInfo/m:copyrightDate')) > 2 
    datestart = len(modsdoc.originInfo.match(xpath = './m:originInfo/*[@point="start"]')) > 0
    s = score(all(d == True for d in [datecount, datestart]), point=False)
    return s

if __name__ == '__main__':

    #create output csv file
    date = time.strftime("%Y-%m-%d")
    filename = 'min-mandatory-score_{0}.csv'.format(date)
    header = ['uuid', 'mms_id', 'mms_type', 'coll_id', 'division', 'title_1', 'title_2', 'title', 'typeOfResource',
              'genre_1', 'genre_2', 'genre', 'date_1', 'date_2', 'date_3', 'date_4', 'date', 'identifier',
              'location_1', 'location_2', 'location_3', 'location_4', 'location_5', 'location', 'total_min_mand']
    w = open(filename, 'wb')
    writer = csv.DictWriter(w, fieldnames=header)
    writer.writeheader()
    
    #log file for failed scoring attempts
    log = open('test_failed-min-mandatory-score_{0}.txt'.format(date), 'wb')
    
    #collections and divisions to omit from audit
    ignore = [25778, 25777]
    resource_types = ["text", "cartographic", "notated music", "sound recording-musical", "sound recording-nonmusical",
                  "sound recording", "still image", "moving image", "three dimensional object", "software, multimedia",
                  "mixed material"]
    ignore_divisions = ['External, not an NYPL item, it comes from some other institution. (LEGACY; Please do not use)',
                        'No Division, NYPL item, but not associated with any one Division, e.g. NYPL Art Work',
                       'Comm, Marketing, and Business Dev', 'Reference and Research Services']


    with open('mms_items.json') as f:
        for idx,line in enumerate(f):
            try:
                row = {}
                line = json.loads(line)
                row['mms_id'] = line['id']
                row['mms_type'] = line['type']
                row['uuid'] = line['uuid']
                mods = line['full_xml']
                try:
                    #2016-07-06: needed to load value of solr_doc_hash as json separately because YAML conversion from Matt's data dump script edit
                    solrhash = json.loads(line['solr_doc_hash'])
                    if 'mms_collection_id' in solrhash:
                        row['coll_id'] = solrhash['mms_collection_id']
                    #works with older data dumps than 2016-06-05
#                     if 'mms_collection_id' in line['solr_doc_hash']:
#                         row['coll_id'] = line['solr_doc_hash']['mms_collection_id']
                    else:
                        row['coll_id'] = ''
                except:
                    row['coll_id'] = ''
                if (row['coll_id'] not in ignore) or (row['coll_id'] == ''):
                    modsdoc = modsqual.Mods(mods)

                    #scores
                    row['title_1'] = exists(modsdoc.titleInfo)
                    row['title_2'] = xpathexactlyone(modsdoc.titleInfo.match(xpath='./m:titleInfo[@usage="primary"]'))
                    row['title'] = sum([row['title_1'], row['title_2']])/2
                    row['typeOfResource'] = inList(modsdoc.typeOfResource, resource_types)
                    row['genre_1'] = exists(modsdoc.genre)
                    row['genre_2'] = xpathexists(modsdoc.genre.match(xpath='./m:genre[@authority]'))
                    row['genre'] = sum([row['genre_1'], row['genre_2']])/2
                    row['date_1'] = xpathexists(modsdoc.originInfo.match(xpath='./m:originInfo/m:dateCreated|./m:originInfo/m:dateIssued|./m:originInfo/m:copyrightDate'))
                    row['date_2'] = xpathexists(modsdoc.originInfo.match(xpath = './m:originInfo/*[@encoding="w3cdtf"]'))
                    row['date_3'] = discretedatetypes(modsdoc.originInfo.match(xpath='./m:originInfo[*[not(@point)]]/m:dateCreated|./m:originInfo[*[not(@point)]]/m:dateIssued'))
                    if row['date_1'] == 1:           
                        row['date_4'] = multiplesingledates(modsdoc)
                    else:
                        row['date_4'] = 0
                    row['date'] = sum([row['date_1'], row['date_2'], row['date_3'], row['date_4']])/4
                    row['identifier'] = xpathexists(modsdoc.identifier.match(xpath='./m:identifier[@type="local_bnumber" or @type="local_mss" or @type="local_tms"]'))
                    row['location_1'] = xpathexists(modsdoc.location.match(xpath='./m:location/m:physicalLocation[@type="repository"]'))
                    row['location_2'] = xpathexists(modsdoc.location.match(xpath='./m:location/m:physicalLocation[@type="division"]'))
                    row['location_3'] = xpathexists(modsdoc.location.match(xpath = './m:location/m:shelfLocator'))
                    row['location_4'] = xpathvaluesmatch(modsdoc.location.match(xpath='./m:location/m:physicalLocation[@type="division"]'))
                    if (row['location_2'] == 1) & (len(modsdoc.location.match(xpath='./m:location/m:physicalLocation[@type="division"]')) > 0):
                        row['division'] = modsdoc.location.match(xpath='./m:location/m:physicalLocation[@type="division"]')[0]['physicalLocation']['#text']
                    else:
                        row['division'] = 'Null'
                    row['location_5'] = xpathexists(modsdoc.location.match(xpath='./m:location[m:physicalLocation[@type="division"] and m:physicalLocation[@type="division_short_name"] and m:physicalLocation[@type="code"]]'))
                    row['location'] = sum([row['location_1'], row['location_2'], row['location_3'], row['location_4']], row['location_5'])/5
                    scores = [row['title'], row['typeOfResource'], row['genre'], row['date'], row['identifier'], row['location']]
                    row['total_min_mand'] = sum(scores)
                    if row['division'] not in ignore_divisions:
                        writer.writerow(row)
            except:
                log.write(str(idx))
                log.write('\n')
    
    log.close()
    w.close()
