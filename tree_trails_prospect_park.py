#!/usr/bin/env python
# coding: utf-8

# # Interactive Tree Trails of Prospect Park
# 
# 
# 
# This notebook walks you through the process of using linked data (with [Wikidata](https://www.wikidata.org)) and natural language processing (with [SpaCy](https://spacy.io/)) to enrich a 1968 book of walking tours of Prospect Park trees, [Tree Trails in Prospect Park](https://www.echonyc.com/~parks/books/treetrailsppk.html), with images and species information for easier identification. It outputs two CSV files suitable for import into two linked [Memento](https://mementodatabase.com/) databases (Android or desktop only). One database will contain information on the tree species (taxon name, common names, links to Wikipedia, Wikimedia Commons for images, and iNaturalist) and the other will contain the stops on the tours linked to the trees featured, with editable fields for you to store your location when you find the tree and any photos you take. Alternatively, you can output two CSV files to create an [Airtable](https://airtable.com/) database (change `formatting` variable to 'airtable' under the "Generating tour stops..." block), though setup is a little more involved and Airtable does not support a geographic coordinates datatype, so you will not be able to store your location. It also doesn't support rich text for data imported through CSV, so you won't see tree species highlighted in the text.
# 
# This process is broken out into the following stages:
# 1. Get a list of all possible tree species and related information from Wikipedia and Wikidata
# 2. Use the SpaCy natural language programming library to locate instances of these trees in the text of the book
# 3. Reshape the text of the book with the tree information into an interactive database 
# 
# You will need to install the following Python libraries (all available with pip):
# - requests
# - lxml
# - jsonlines
# - spacy
# 
# If you want to skip directly to installing and loading the data, follow the instructions in [importing-database-data.md](importing-database-data.md).

#You may need to install the requests, lxml, jsonlines, and spacy libraries before you start. All can be installed with pip.

import requests
import csv
import json
import time
from lxml import etree as et
import jsonlines
import re
import spacy
from spacy.pipeline import EntityRuler


# ## Get a list of tree species
# 
# There isn't a great way to query Wikidata for all tree species, so I scraped all listed species from this [Wikpedia list of trees and shrubs by taxonomic family](https://en.wikipedia.org/wiki/List_of_trees_and_shrubs_by_taxonomic_family) using lxml's xpath() function to get the Wikipedia article titles and species names.

#use lxml's HTMLParser to put the html content into a searchable tree structure
parser = et.HTMLParser()
html = requests.get('https://en.wikipedia.org/wiki/List_of_trees_and_shrubs_by_taxonomic_family').content
tree = et.fromstring(html, parser)

#limit results to all table row (<tr>) elements in the html
rows = tree.xpath('//tr')

#Within each <tr>, the first table data (<td>) element contains the species information we need, so add each of those to a list
species = []
for row in rows:
    if len(row.xpath('td')) > 0:
        s = row.xpath('./td')[0]
        species.append(s)

#Within each of these <td> elements, the species name and Wikipedia links are in the @title and @href attributes
tree_species = []
for s in species:
    if len(s.xpath('a/@href')) > 0:
        #extract the name and wiki_link from each of the results matching the xpath above
        ts = {}
        ts['name'] = s.xpath('a/@title')[0]
        ts['wiki_link'] = s.xpath('a/@href')[0]
        #except some of these pages are not species, so skip those
        if ts['name'] not in ['Least-concern species', 'Vulnerable species', 'Endangered species', 'Critically endangered']:
            tree_species.append(ts)
    


# ### Get Wikidata ids for each tree species
# 
# With the Wikipedia article names from the scraped list, you can use the Wikipedia API to get the corresponding Wikidata id.

def getWikidataId(wp_id):
    """Get Wikidata id for a given Wikipedia article title"""
    base = 'https://en.wikipedia.org/w/api.php?action=query&prop=pageprops&ppprop=wikibase_item&redirects=1&format=json&titles='
    url = base + wp_id
    query = requests.get(url)
    wd_id = None
    response = json.loads(query.content)
    for k, v in response['query']['pages'].items():
        if 'pageprops' in v:
            wd_id = v['pageprops']['wikibase_item']
    return wd_id

#Call the API to get the corresponding wikidata id and add it to the tree species entry
for ts in tree_species:
    base = 'https://en.wikipedia.org'
    #some trees do not have wikipedia pages, so ignore these
    if 'page does not exist' not in ts['name']:
        wd_id = getWikidataId(ts['name'])
        if wd_id is not None:
            ts['wikidata'] = wd_id
    #Use a 1 second rate limit in between queries
    time.sleep(1)

#saving as we go
f = open('tree_species.json', 'w')
json.dump(tree_species, f)
f.close()


# Some species in our text aren't in this list because they are cultivars or technically not trees, so we'll add them now:

addtl_wiki_ids = [{'name': "Ulmus glabra 'Camperdownii'", 'wikidata': 'Q7879447'},
{'name': 'Clethra alnifolia', 'wikidata': 'Q5131966'},
{'name': 'Picea orientalis', 'wikidata': 'Q1145286'},
{'name': 'Pinus densiflora umbraculifera', 'wikidata': 'Q74534097'},
{'name': 'Ulmus carpinifolia', 'wikidata': 'Q3547946'},
{'name': 'Ilex crenata', 'wikidata': 'Q1328685'},
{'name': 'Euonymus kiautschovica', 'wikidata': 'Q15226197'},
{'name': 'Magnolia soulangeana', 'wikidata': 'Q731443'},
{'name': 'Aesculus carnea', 'wikidata': 'Q163779'}]

tree_species.extend(addtl_wiki_ids)


# Deduplicate this list, just in case

tree_species = [dict(t) for t in {tuple(d.items()) for d in tree_species}]


# ### Get Wikidata info on Species: name, common names, Wikipedia Commons link, and iNaturalist id
# 
# With the Wikidata ids, use SPARQL to [query Wikidata](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial) at the [Wikidata Query Service (WDQS)](https://query.wikidata.org/) for each, retrieving species name, alt label, common names, Wikimedia Commons page (useful for images), and iNaturalist id (for more info and local observations of the species). You can get any ids you want from the Wikidata page, such as NCBI taxonomy ID, USDA Plants ID, or many more. I chose iNaturalist because of the easy interface to photos, commmon names, and local observations. If you want to get additional identifiers or properties back in your query, you can adjust the query below by adding a statement to the WHERE clause similar to `OPTIONAL {{ {} wdt:P3151 ?inaturalist. }}` where `P3151` is the property you want retrieve and `?inaturalist` is a variable name of your choice to represent the property value. Append "Label" to the end of this variable and add it to the SELECT clause to return the value in your query results, (ex. `?inaturalistLabel`). The "OPTIONAL" clause ensures that all of the other results your requesting for the species will be returned even if the value of this property isn't present.  

def getWikidataBySpecies(request_id):
    """Function to retrive items and properties by tree species id through the WDQS."""
    #Add additional properties within the select clause as desired
    wdid = 'wd:' + request_id
    #doubled curly braces are used here instead of single because you're sending the query using REST
    sparql = """PREFIX wikibase: <http://wikiba.se/ontology#>
            PREFIX wd: <http://www.wikidata.org/entity/>
            PREFIX wdt: <http://www.wikidata.org/prop/direct/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?label ?altLabel ?commonLabel ?inaturalistLabel ?wpcommonsLabel
            WHERE 
            {{
              {} rdfs:label ?label .
                FILTER (langMatches( lang(?label), "EN" ) )
              OPTIONAL {{ {} skos:altLabel ?altLabel FILTER ( lang(?altLabel) = "en" ). }}
              OPTIONAL {{ {} wdt:P3151 ?inaturalist. }}
              OPTIONAL {{ {} wdt:P1843 ?common filter (lang(?common) = "en").}}
              OPTIONAL {{ {} wdt:P935 ?wpcommons. }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
            }}
            """.format(wdid, wdid, wdid, wdid, wdid)
    base = "https://query.wikidata.org/bigdata/namespace/wdq/sparql"
    headers = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    query = requests.post(base, headers=headers, params={'query': sparql, 'format': 'json'})
    #store and return the request information and data in a dict
    request = {}
    request['request_id'] = request_id
    request['sparql_query'] = sparql
    request['status_code'] = query.status_code
    if query.status_code == 200:
        request['data'] = query.json()
    else:
        request['data'] = None
    return request

def parseWikidataBySpecies(response):
    """Parse the wikidata response and put it into a more readable dict"""
    results = {}
    #add results from each binding to list for each property, then dedupe each list before returning value
    for b in response['data']['results']['bindings']:
        for k, v in b.items():
            if k in results:
                results[k].append(v['value'])
            else:
                results[k] = [v['value']]
    for k, v in results.items():
        results[k] = list(set(v))
    return results

def reshapeWikidata(tree_species):
    """Reshape all of the tree species data into more usable data"""
    for ts in tree_species:
        #expand links into full URLs
        if 'wiki_link' in ts:
            ts['wikipedia'] = 'https://en.wikipedia.org/' + ts['wiki_link']
        #remove wikipedia links and '(page does not exist)' from species without wikipedia pages
        if '(page does not exist)' in ts['name']:
            ts.pop('wikipedia')
            ts['name'] = ts['name'].replace(' (page does not exist)', '')
        if 'raw_wd' in ts:
            wd_data = parseWikidataBySpecies(ts['raw_wd'])
            #make the inaturalist ids and WM commons ids into urls
            if 'inaturalistLabel' in wd_data:
                ts['inaturalist'] = 'https://inaturalist.org/taxa/' + wd_data['inaturalistLabel'][0]
            if 'wpcommonsLabel' in wd_data:
                ts['wp_commons'] = 'https://commons.wikimedia.org/wiki/' + wd_data['wpcommonsLabel'][0]
            if 'label' in wd_data:
                ts['species'] = wd_data['label'][0]
            #combine altLabels and common names into a single list
            ts['common_names'] = []
            if 'altLabel' in wd_data:
                ts['common_names'].extend(wd_data['altLabel'])
            if 'commonLabel' in wd_data:
                ts['common_names'].extend(wd_data['commonLabel'])
            #convert all common names to title case and dedupe
            ts['common_names'] = [c.title() for c in ts['common_names']]
            ts['common_names'] = list(set(ts['common_names']))
    return tree_species

def writeSpeciesToCsv(tree_species):
    """Write the data out to a csv file suitable for import into a database"""
    c = open('tree_species.csv', 'w')
    fieldnames = ['Species', 'Common names', 'Images', 'Wikipedia', 'Wikimedia Commons', 'iNaturalist']
    writer = csv.DictWriter(c, fieldnames=fieldnames)
    writer.writeheader()
    for ts in tree_species:
        row = {}
        row['Species'] = ts['name']
        if 'common_names' in ts:
            row['Common names'] = ', '.join(ts['common_names'])
        if 'inaturalist' in ts:
            row['Images'] = ts['inaturalist'] + '/browse_photos'
        if 'wikipedia' in ts:
            row['Wikipedia'] = ts['wikipedia']
        if 'wp_commons' in ts:
            row['Wikimedia Commons'] = ts['wp_commons']
        if 'inaturalist' in ts:
            row['iNaturalist'] = ts['inaturalist']
        writer.writerow(row)
    c.close()

#query wikidata for each species (using a respectable rate limit).
for ts in tree_species:
    if 'wikidata' in ts:
        wd = getWikidataBySpecies(ts['wikidata'])
        ts['raw_wd'] = wd
        time.sleep(1)

#saving as we go        
f = open('tree_species.json', 'w')
json.dump(tree_species, f)
f.close()


# Reshape the raw Wikidata results into a more structured form

tree_species = reshapeWikidata(tree_species)


# Some common names and alternate species names are in the Tree Trails text but not our tree species list, so we'll add them here. (I added quite a few to Wikidata as I was working on this project, but I didn't add any that seemed like they weren't commonly accepted common names, i.e. not in the Wikipedia article or on the first page of a google search.)

addtl_names = [{'wikidata': 'Q1328685', 'alt_species': 'Ilex crenata convexa'},
{'wikidata': 'Q161374', 'alt_species': 'Planatus acerifolia'},
{'wikidata': 'Q288558', 'alt_species': 'Sophora'},
{'wikidata': 'Q161166', 'common_name': 'Box elder'},
{'wikidata': 'Q161382', 'common_name': 'Silver-leafed linden'},
{'wikidata': 'Q147525', 'common_name': 'Low-branched red oak'},
{'wikidata': 'Q165137', 'common_name': 'European cherry'},
{'wikidata': 'Q3125935', 'common_name': 'Two-trunked silverbell'},
{'wikidata': 'Q26745', 'common_name': 'Schwedler maple'},
{'wikidata': 'Q549418', 'common_name': 'Kentucky coffee tree'},
{'wikidata': 'Q1328685', 'common_name': 'Boxleaf holly'},
{'wikidata': 'Q74534097', 'common_name': 'Tanyosho pine'},
{'wikidata': 'Q7879447', 'common_name': 'Camperdown elm'},
{'wikidata': 'Q5131966', 'common_name': 'Sweet pepperbush'},
{'wikidata': 'Q1145286', 'common_name': 'Oriental spruce'},
{'wikidata': 'Q74534097', 'common_name': 'Japanese umbrella pine'},
{'wikidata': 'Q3547946', 'common_name': 'Smooth-leaved elm'},
{'wikidata': 'Q1683340', 'common_name': 'Chinese tree lilac'},
{'wikidata': 'Q1328685', 'common_name': 'Japanese holly'},
{'wikidata': 'Q731443', 'common_name': 'Saucer magnolia'},
{'wikidata': 'Q26899', 'common_name': 'European horsechestnut'},
{'wikidata': 'Q288558', 'common_name': 'Pagoda tree'},
{'wikidata': 'Q3547946', 'common_name': 'Smooth-leafed elm'},
{'wikidata': 'Q158746', 'common_name': 'Small-leafed linden'},
{'wikidata': 'Q158746', 'common_name': 'Small-leaf European linden'},              
{'wikidata': 'Q163760', 'common_name': 'European linden'},
{'wikidata': 'Q157230', 'common_name': 'White pine'},
{'wikidata': 'Q549418', 'alt_species': 'Gymnocladus dioicus'},
{'wikidata': 'Q24877919', 'common_name': 'Chinese tree lilac'},
{'wikidata': 'Q163779', 'common_name': 'Pink-flowering horsechestnut'},
{'wikidata': 'Q161374', 'alt_species': 'Platanus acerifolia'},
{'wikidata': 'Q470006', 'common_name': 'Hackberry'}]

for a in addtl_names:
    for t in tree_species:
        if 'wikidata' in t:
            if a['wikidata'] == t['wikidata']:
                if 'common_name' in a:
                    if 'common_names' in t:
                        t['common_names'].append(a['common_name'])
                    else:
                        t['common_names'] = [a['common_name']]
                elif 'alt_species' in a:
                    t['alt_species'] = [a['alt_species']]


# Some names from Wikidata are duplicated across species and will result in associating the wrong tree with a name.

remove_name = [{'wikidata': 'Q1988747', 'common_name': 'White pine'},
{'wikidata': 'Q1981615', 'common_name': 'White pine'},
{'wikidata': 'Q2724971', 'species': 'Prunus nigra'},
{'wikidata': 'Q147064', 'species': 'Populus nigra'},
{'wikidata': 'Q1683340', 'species': 'Syringa reticulata'},
{'wikidata': 'Q1981615', 'species': 'Dacrycarpus dacrydioides'},
{'wikidata': 'Q27344', 'species': 'Buxus hyrcana'},
{'wikidata': 'Q158987', 'species': 'Prunus salicifolia'},
{'wikidata': 'Q147498', 'species': 'Ulmus glabra'}]

entity_remove = []
for i, ts in enumerate(tree_species):
    for r in remove_name:
        if 'wikidata' in ts:
            if ts['wikidata'] == r['wikidata']:
                if 'common_name' in r:
                    ts['common_names'] = [c for c in ts['common_names'] if c != r['common_name']]
                if 'species'in r:
                    if r['species'] == ts['name']:
                        entity_remove.append(i)
tree_species = [ts for i, ts in enumerate(tree_species) if i not in entity_remove]


# ## Extract species from Tree Trails text

# ### Create the data matching rules
# Make a SpaCy patterns.jsonl file from the tree species data with all possible variations on the text strings we want to extract from the book text--singular or plural common names, full or abbreviated species names.

def pluralize(text):
    """Get the plural form of a singular noun"""
    if text.endswith('y'):
        text = text.replace('y', 'ies')
    elif text.endswith(('ch', 's', 'sh', 'z', 'x')):
        text = text + 'es'
    else:
        text = text + 's'
    return text

def tokenHyphen(text):
    """Tokenize hyphenated words into SpaCy patterns"""
    tokens = text.split('-')
    patterns = []
    pattern1 = {}
    pattern1['LOWER'] = tokens[0].lower()
    patterns.append(pattern1)
    hyphen = {}
    hyphen['ORTH'] = '-'
    patterns.append(hyphen)
    pattern2 = {}
    pattern2['LOWER'] = tokens[1].lower()
    patterns.append(pattern2)
    return patterns

def constructTerm(term, label, id):
    """Create all the patterns needed for matching any variations on a tree species name"""
    termlist = []
    if term != '': 
        listitem = {}
        listitem['label'] = label
        listitem['id'] = id
        patterns = []
    #for labels that are tree species or alternate names for tree species
    if label in ['TREE SPECIES', 'ALT TREE SPECIES']:
        for s in term.split(' '):
            pattern = {}
            #we will lowercase all words in the text and in patterns so we don't have to worry abut case matching
            pattern['LOWER'] = s.lower()
            patterns.append(pattern)
        listitem['pattern'] = patterns
        termlist.append(listitem.copy())
        #create a pattern with genus abbreviated, ex. "p. strobus"
        altitem = {}
        altitem['label'] = label
        altitem['id'] = id
        altpatterns = []
        for i, s in enumerate(term.split(' ')):
            altpattern = {}
            if i == 0:
                altpattern['LOWER'] = s[0].lower() + '.'
                altpatterns.append(altpattern)
            else:
                altpattern['LOWER'] = s.lower()
                altpatterns.append(altpattern)
        altitem['pattern'] = altpatterns
        termlist.append(altitem.copy())
    #for the labels that are common names, add patterns for matching pluralized form in addition to singular 
    elif label == 'TREE COMMON NAME':
        for i, s in enumerate(term.split(' ')):
            if '-' in s:
                hyphenpatterns = tokenHyphen(s)
                patterns.extend(hyphenpatterns)
            else:
                pattern = {}
                pattern['LOWER'] = s.lower()
                patterns.append(pattern)
        listitem['pattern'] = patterns
        termlist.append(listitem.copy())
        patterns = []
        for i, s in enumerate(term.split()):
            pattern = {}
            #pluralize only the last token in the word
            if i != len(term.split())-1:
                if '-' in s:
                    hyphenpatterns = tokenHyphen(s)
                    patterns.extend(hyphenpatterns)
                else:
                    pattern['LOWER'] = s.lower()
                    patterns.append(pattern)
            else:
                pattern['LOWER'] = pluralize(s.lower())
                patterns.append(pattern)
        listitem['pattern'] = patterns
        termlist.append(listitem)
    else:
        listitem = None
    return termlist

#create patterns file while also adding ids to tree species objects. If a Wikidata id doesn't exist, add an 
#auto-incrementing alt_id
termlist = []
alt_id = 1
for t in tree_species:
    if 'wikidata' in t:
        id = t['wikidata']
        t['id'] = t['wikidata']
    else:
        id = 'x' + str(alt_id)
        t['id'] = id
    #create the patterns for tree species taxon names
    term = constructTerm(t['name'], 'TREE SPECIES', id)
    if term is not None:
        termlist.extend(term)
    #create the patterns for common names
    if 'common_names' in t:
        for c in t['common_names']:
            c_term = constructTerm(str(c), 'TREE COMMON NAME', id)
            if c_term is not None:
                termlist.extend(c_term)
    #create the patterns for alternate species names
    if 'alt_species' in t:
        for a in t['alt_species']:
            a_term = constructTerm(str(a), 'ALT TREE SPECIES', id)
            if a_term is not None:
                termlist.extend(a_term)
    if 'wikidata' not in t:
        alt_id += 1

ts_out = open('tree_species.json', 'w')
json.dump(tree_species, ts_out)
ts_out.close()

#save the patterns for SpaCy as a new-line delimited json file (.jsonl)
termlistname = 'patterns.jsonl'
f = open(termlistname, 'a')
writer = jsonlines.Writer(f)
writer.write_all(termlist)
writer.close()
f.close()


# ### Get the Tree Trails book text
# The full text of Tree Trails is provided by the publisher at https://www.echonyc.com/~parks/books/treetrailsppk.html. We will scrape the html from that page and convert it to plain text with the Python lxml library.

query = requests.get('https://www.echonyc.com/~parks/books/treetrailsppk.html')

#convert html to plain text
parser = et.HTMLParser()
tree = et.fromstring(query.content, parser)
text = et.tostring(tree, method='text', encoding='unicode')


# There are a few typos in the online version of the text that will affect the text recognition, so let's fix those now.

typos = [{'find': 'Comus florida', 'replace':'Cornus florida'},
        {'find': 'anwricana', 'replace':'americana'},
        {'find': 'veluntina', 'replace':'velutina'},
        {'find': 'Uhnus procera', 'replace':'Ulmus procera'},
        {'find': 'Tilia europea', 'replace': 'Tilia europaea'},
        {'find': 'P. onentalis', 'replace': 'P. orientalis'},
        {'find': 'P. strobits', 'replace': 'P. strobus'}]

for t in typos:
    text = text.replace(t['find'], t['replace'])


# ### Locate species in text
# This step uses Spacy's [EntityRuler](https://spacy.io/usage/rule-based-matching#entityruler) for rule-based matching on the patterns we created above in the patterns.jsonl file. In this NLP pipeline, we will also identify sentences, so we can group them into paragraphs.

#create a blank SpaCy pipeline
nlp = spacy.blank('en')
#create an instance of the EntityRuler to add to our pipeline below
ruler = EntityRuler(nlp)
#load the custom vocabs from the appropriate patterns.jsonl
patternfile = 'patterns.jsonl'
ruler.from_disk(patternfile)
#add a pipe in our nlp pipeline to identify the sentences in the text
nlp.add_pipe(nlp.create_pipe('sentencizer'))
#add a pipe in our nlp pipeline for the EntityRuler to match our patterns
nlp.add_pipe(ruler)

#run the text through the nlp pipeline
doc = nlp(text)

#get entity information from the nlp process. save entities, ids, and character offsets for later use
ents = []
for e in doc.ents:
    ent = {}
    ent['text'] = e.text
    ent['start_char'] = e.start_char
    ent['end_char'] = e.end_char
    ent['id'] = e.ent_id_
    ent['spacy_id'] = e.ent_id
    ent['label'] = e.label_
    ents.append(ent)

#save sentences and their character offsets in a list
sents = []
for s in doc.sents:
    sent = {}
    sent['text'] = s.text
    sent['start_char'] = s.start_char
    sent['end_char'] = s.end_char
    sents.append(sent)


# ## Split text and tree data by paragraph
# With entities and sentences identified, we will now break the text up into its introduction, four tours, and back matter and then group sentences into paragraphs, or "stops" on each tour.

#first, split text by the word "TOUR" and "FOOTNOTE". The first segment will be front matter/introduction and the 
#last segment will be back matter. Everything in between is a tour.
sections = []
section = []
for s in sents:
    if ('TOUR' not in s['text']) and ('FOOTNOTE' not in s['text']):
        section.append(s)
    else:
        sections.append(section)
        section = []
        section.append(s)
sections.append(section)

#assign tour names to relevant sections
tours = {}
tours['intro'] = {}
tours['intro']['sents'] = sections[0]
tours['1'] = {}
tours['1']['sents'] = sections[1]
tours['2'] = {}
tours['2']['sents'] = sections[2]
tours['3'] = {}
tours['3']['sents'] = sections[3]
tours['4'] = {}
tours['4']['sents'] = sections[4]
tours['back_matter'] = {}
tours['back_matter']['sents'] = sections[5]


# For each tour section, break into paragraphs based on "\n\n"

#split each section into paragraphs based on '\n\n' and add to tours dict
for k, t in tours.items():
    t['paragraphs'] = []
    p = {}
    p['sents'] = []
    for s in t['sents']:
        if not(re.match(r'\n\n', s['text'])):
            p['sents'].append(s)
        else:
            if len(p['sents']) > 0:
                t['paragraphs'].append(p.copy())
            p = {}
            p['sents'] = []
            p['sents'].append(s)
    t['paragraphs'].append(p)
    #add start and end char offsets for each paragraph
    for p in t['paragraphs']:
        p['start_char'] = p['sents'][0]['start_char']
        p['end_char'] = p['sents'][-1]['end_char']


# For each paragraph, find the corresponding entities (in tours only) by checking entity character offsets that fall within the paragraph character offsets.

#find entities within each paragraph by checking if each entity's starting character offset is within the paragraph offsets
for k, t, in tours.items():
    #only find entities in the tours, not the introduction or back matter
    if k not in ['intro', 'back_matter']:
        for p in t['paragraphs']:
            p['ents'] = []
            for e in ents:
                if e['start_char'] in range(p['start_char'], p['end_char']):
                    p['ents'].append(e)


# There might be multiple mentions of a species or its common name within a paragraph, so we'll assume they're talking about the same tree and group them. For some common names, if a species isn't reference in a paragraph, we will look it up in the tree_species list and add group it with the common name.

def getCommonBySpeciesId(id, tree_species):
    common_names = []
    for ts in tree_species:
        if (ts['id'] == ent['id']):
            #check if the matched tree species has common names
            if 'common_names' in ts:
                for cn in ts['common_names']:
                    common_names.append(cn)
    return common_names

#merge entities with same id within each paragraph, including common names that match tree species in the paragraph and ignoring single common names with no corresponding species
for k, t, in tours.items():
    for p in t['paragraphs']:
        p['merged_ents'] = {}
        if 'ents' in p:
            for e in p['ents']:
              #first add the species
              if e['label'] == 'TREE SPECIES':
                if e['id'] not in p['merged_ents']:
                    p['merged_ents'][e['id']] = [e]
                else:
                    p['merged_ents'][e['id']].append(e)
            for e in p['ents']:
              #only include single-token names if they have a corresponding species (single-token name might be too general to be an accurate match)
              if e['label'] == 'TREE COMMON NAME':
                if ' ' not in e['text']:
                    if e['id'] in p['merged_ents']:
                        p['merged_ents'][e['id']].append(e)
                #if multi-token names have a corresponding species, add to that list
                elif e['id'] in p['merged_ents']:
                    p['merged_ents'][e['id']].append(e)
                else:
                    #if not, then check the common name against common names of other species in the paragraph and
                    #get the list of entity ids in the paragraph
                    common = {}
                    #iterate through each id
                    for ent in p['ents']:
                        if ent['label'] == 'TREE SPECIES':
                            if len(common) == 0:
                                cn = getCommonBySpeciesId(ent['id'], tree_species)
                                for c in cn:
                                    #title case the name and check if it matches the singular or plural form of the common name
                                    if e['text'].title().replace("'S", "'s") in [pluralize(c.title().replace("'S", "'s")), c.title().replace("'S", "'s")]:
                                        #if so, add it and its tree species to the list
                                        common = [{'text':e['text'], 'label':'TREE COMMON NAME', 'id':ent['id'], 'start_char':e['start_char']},
                                                  {'text':ent['label'], 'label':'TREE SPECIES', 'id':ent['id']}]
                                        if ent['id'] in p['merged_ents']:
                                            p['merged_ents'][ent['id']].extend(common)
                                        else:
                                            p['merged_ents'][ent['id']] = common
                    #otherwise, check the common names of species in the paragraph against tree_species
                    if len(common) == 0:
                        species = {}
                        for ts in tree_species:
                            if e['id'] == ts['id']:
                                species = [{'text':ts['name'], 'label':'TREE SPECIES', 'id':e['id']},
                                           {'text':e['text'], 'label':'TREE COMMON NAME', 'id':e['id'], 'start_char':e['start_char']}]
                        p['merged_ents'][e['id']] = species


# ### Generate tour "stops" with title, lead-in, rich text book excerpt, tour number, and id to use for linking to tree species list
# For each tour stop entry in the database, we want a title (the taxon name of the tree), a lead-in to display below the title (the first 35 characters of the paragraph), the book excerpt paragraph with tree species bold and italic, common names italic and both displayed in a difference color, tour number for filtering, and the species name to link to the tree species dataset.

# Change the value of the `formatting` value below to 'airtable' if you want to output CSV files for import into Airtable, which doesn't allow for rich text, instead of Memento.

formatting = 'memento'

def bold(text, formatting='memento'):
    if formatting == 'memento':
        text = '<b>' + text + '</b>'
    return text

def italic(text, rgb='156, 39, 176', formatting='memento'):
    if formatting == 'memento':   
        if rgb is not None:
            color = 'style="color: rgb({});"'.format(rgb)
            text = '<i {}>'.format(color) + text + '</i>'
        else:
            text = '<i>' + text + '</i>'
    return text

def lineBreaks(text, formatting='memento'):
    """Format line breaks consistently"""
    #strip line breaks at the start of a stop
    lbs = re.compile('\xa0')
    text = re.sub(lbs, '', text)
    stopstart = re.compile('^\n+')
    text = re.sub(stopstart, '', text)
    #replace excessive linebreaks with double line break
    lb = re.compile('\n\n+')
    text = re.sub(lb, '\n\n', text)
    return text

def joinSents(sents):
    """Join sentences with consistent spacing"""
    text = ' '.join([s['text'] for s in sents])
    spacing = re.compile(' +')
    text = re.sub(spacing, ' ', text)
    return text

def createTitle(merged_ent):
    """Make the title the common name followed by the species in parentheses, or just the species, if the common name 
    doesn't appear in the paragraph"""
    species = None
    commons = []
    for m in merged_ent:
        #add any common names to a list
        if m['label'] == 'TREE COMMON NAME':
            commons.append(m['text'])
        #get full tree species name
        for ts in tree_species:
            if m['id'] == ts['id']:
                species = ts['name']
    commons = list(set(commons))  
    if len(commons) > 0:
        #use the first common name in the common name list as the title
        title = commons[0].capitalize()
        #add the species in parentheses after the common name
        if species is not None:
            title = title + ' (' + species.capitalize() + ')'
    elif species is not None:
        title = species.capitalize()
    return title

def createExcerpt(paragraph, merged_ent):
    """Convert paragraphs into rich text, bolding and/or italicizing tree names"""
    #get unique entities and labels
    u_ents = {}
    for m in merged_ent:
        if m['label'] in u_ents:
            if m['text'] not in u_ents[m['label']]:
                u_ents[m['label']].append(m['text'])
        else:
            u_ents[m['label']] = [m['text']]
    p_text = joinSents(paragraph['sents'])
    #join sentences
    excerpt = lineBreaks(p_text, formatting=formatting)
    for k, u in u_ents.items():
        if k in ['TREE SPECIES', 'ALT TREE SPECIES']:
            for text in u:
                excerpt = excerpt.replace(text, bold(italic(text, formatting=formatting), formatting=formatting))
        if k == 'TREE COMMON NAME':
            for text in u:
                excerpt = excerpt.replace(text, italic(text, formatting=formatting))
    return excerpt

def getSpecies(merged_ent, tree_species):
    """Get the tree species name for an entity"""
    species = None
    for m in merged_ent:
        if m['label'] == 'TREE SPECIES':
            for ts in tree_species:
                if m['id'] == ts['id']:
                    species = ts['name']
    return species

def createLeadIn(p):
    """Use the first 35 characters as a lead-in field to use in the card description"""
    leadin = p['sents'][0]['text'].replace('\n', ' ').strip()[0:35] + '...'
    return leadin

def createStop(paragraph, merged_ent, id, tree_species):
    """Create all the database fields for a tour stop for each merged entity in a paragraph"""
    stop = {}
    stop['title'] = createTitle(merged_ent)
    stop['lead-in'] = createLeadIn(paragraph)
    stop['excerpt'] = createExcerpt(paragraph, merged_ent)
    stop['species'] = getSpecies(merged_ent, tree_species)
    return stop

def appendNoEntPara(stops, p):
    """If there are no entities in a paragraph, append it to the previous stop (or stops if the last para was
    broken up into multiple stops)"""
    prev_stop = -2
    p_text = '\n\n' + joinSents(p['sents'])
    stops[-1]['excerpt'] = lineBreaks(stops[-1]['excerpt'] + p_text, formatting=formatting)
    #append it to all previous stops with the same lead-in, for previous paragraphs repeated for multiple entities
    if len(stops) > 1:
        while stops[prev_stop]['lead-in'] ==  stops[-1]['lead-in']:
            #re-run it through lineBreaks() after adding to remove any errant formatting
            stops[prev_stop]['excerpt'] = lineBreaks(stops[prev_stop]['excerpt'] + p_text, formatting=formatting)  
            prev_stop = prev_stop - 1
    return stops

def writeStopsToCsv(stops, out):
    """Write the data out to a csv file suitable for import into the database"""
    fieldnames = ['Name', 'Description', 'Excerpt', 'Tree species', 'Tour', 'Sequence']
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    for s in stops:
        row = {}
        row['Name'] = s['title']
        row['Excerpt'] = s['excerpt']
        row['Description'] = s['lead-in']
        if 'species' in s:
            row['Tree species'] = s['species']
        row['Tour'] = s['tour']
        row['Sequence'] = s['sequence']
        writer.writerow(row)
    out.close()  


# ### Create tour "stops" for each merged entity in each paragraph
# Iterate through each paragraph in each tour. For the Introduction, all paragraphs will go into one stop, after a little extra data clean-up. For Tours, if there are multiple different tree species in a paragraph, the paragraph will get repeated as a stop for each tree species, so that you can add separate geocoordinates and images for each tree. If a paragraph has no tree species, then it will be appended to the previous stop (or stops, if the previous paragraph contained multiple tree species). 

stops = []


# #### Process front matter

for k, t in tours.items():
    tour = k
    #for title page/colophon 
    if k == 'intro':
        fm_p = None
        #find all front matter before the table of contents and the Marianne Moore poem, which is under a different copyright
        for i, p in enumerate(t['paragraphs']):
            fmp_text = joinSents(p['sents'])
            if 'TABLE' in fmp_text:
                fm_p = i
        front_matter_p = t['paragraphs'][0:fm_p]
        #only use text after the web page header
        for i, fs in enumerate(front_matter_p):
            for j, fss in enumerate(fs['sents']):
                if 'Tree Trails in Prospect Park' in fss['text']:
                    front_matter_p[i]['sents'][i]['text'] = 'Tree Trails in Prospect Park' + front_matter_p[i]['sents'][i]['text'].split('Tree Trails in Prospect Park')[1]
        fm_texts = []
        #join all sentences in the front matter, omitting any text up to and including 'TABLE'
        for fmp in front_matter_p:
            fm_text = [s['text'] for s in fmp['sents']]
            for f in fm_text:
                if 'TABLE' in f:
                    f = f.split('TABLE')[0]
                fm_texts.append(f) 
        fm = lineBreaks(''.join(fm_texts), formatting=formatting)
        #create the stop for the front_matter
        stop = {}
        stop['title'] = 'Front Matter'
        stop['lead-in'] = fm[0:30] + '...'
        stop['excerpt'] = fm
        stop['tour'] = 'Introduction'
        stops.append(stop.copy())
        #get the paragraphs in the introduction, after the poem
        intro_p = None
        #find the paragraph with "INTRODUCTION", so we can use all text after that for the intro
        for i, p in enumerate(t['paragraphs']):
            p_text = joinSents(p['sents'])
            if 'INTRODUCTION' in p_text:
                intro_p = i
        intro_paragraphs = t['paragraphs'][intro_p:]
        texts = []
        #join all sentences in the intro, omitting any text up to and including 'INTRODUCTION'
        for p in intro_paragraphs:
            text = [s['text'] for s in p['sents']]
            for t in text:
                if 'INTRODUCTION' in t:
                    t = t.split('INTRODUCTION')[1]
                texts.append(t)   
        #join while cleaning up line breaks and whitespace
        p_text = lineBreaks(''.join(texts))
        #create the stops for the intro
        stop = {}
        stop['title'] = 'INTRODUCTION'
        stop['lead-in'] = p_text[0:35] + '...'
        stop['excerpt'] = p_text
        stop['tour'] = 'Introduction'
        stops.append(stop.copy())


# #### Process tours

for k, t in tours.items():
    tour = k
    #for intro 
    if k not in ['intro', 'back_matter']:
        for p in t['paragraphs']:
            if 'merged_ents' not in p:
                p['merged_ents'] = {}
            #if there are no entities in the paragraph, then append the paragraph text to the previous stop excerpt, unless it contains "TOUR"
            if len(p['merged_ents']) == 0:
                if 'TOUR' not in joinSents(p['sents']):
                    if len(stops) > 0:
                        stops = appendNoEntPara(stops, p)
                else:
                    stop = {}
                    stop['title'] = 'TOUR ' + k            
                    p_text = joinSents(p['sents'])
                    #if there is other text in this paragraph before the tour name, split it out and append it to the previous stop(s)
                    if 'TOUR' in p_text:
                        p_text = 'TOUR' + p_text.split('TOUR')[1]
                        to_prev = {'sents':[{'text':p_text.split('TOUR')[0]}]}
                        appendNoEntPara(stops, to_prev)
                    stop['lead-in'] = lineBreaks(p_text[0:35] + '...', formatting=formatting)
                    stop['excerpt'] = lineBreaks(p_text, formatting=formatting)
                    stop['tour'] = 'TOUR ' + tour
                    stops.append(stop.copy())
            #create stop for each merged ent in a paragraph
            else:
                if 'merged_ents' in p:
                    #order merged_ents by earliest offsets
                    merged_ents = []
                    ordered_ents = []
                    for k, v in p['merged_ents'].items():
                        if len(v) > 0:
                            m_ent = {}
                            m_ent['id'] = k
                            m_ent['earliest_start_char'] = min([d['start_char'] for d in v if 'start_char' in d])
                            m_ent['ents'] = v
                            merged_ents.append(m_ent)
                        ordered_ents = sorted(merged_ents, key=lambda k: k['earliest_start_char']) 
                    for o in ordered_ents:
                        stop = createStop(p, o['ents'], o['id'], tree_species)
                        stop['tour'] = 'TOUR ' + tour
                        stops.append(stop.copy())


# #### Process back matter

for k, t in tours.items():
    tour = k
    #for back matter
    if k == 'back_matter':
        bm_p = None
        #split out the FOOTNOTE... and WORD ABOUT THE AUTHOR into two sections
        footnote = []
        wordabout = []
        #find the paragraph indexes for each
        for i, p in enumerate(t['paragraphs']):
            bmp_text = joinSents(p['sents'])
            if 'FOOTNOTE' in bmp_text:
                fn_p = i
            if 'WORD ABOUT' in bmp_text:
                wa_p = i
        #split by index and add to separate lists
        for i, p in enumerate(t['paragraphs'][0:wa_p]):
            fnp_text = ''.join([s['text'] for s in p['sents']])
            if 'FOOTNOTE' in fnp_text:
                #add the text before the 'FOOTNOTE' to the previous stop's excerpt
                to_prev = {'sents':[{'text':fnp_text.split('FOOTNOTE')[0]}]}
                appendNoEntPara(stops, to_prev)
                #add the rest to the footnotes list of paragraphs
                fnp_text_rest = {'sents':[{'text':'FOOTNOTE' + fnp_text.split('FOOTNOTE')[1]}]}
                footnote.append(joinSents(fnp_text_rest['sents']))
            else:
                footnote.append(joinSents(p['sents']))
        #join all of the sents for the footnote
        fn = lineBreaks(''.join(footnote), formatting=formatting)
        #create the stop for the footnote
        stop = {}
        stop['title'] = 'FOOTNOTE TO TREE TRAILS'
        stop['lead-in'] = fn[0:35] + '...'
        stop['excerpt'] = fn
        stop['tour'] = 'Back matter'
        stops.append(stop.copy())
        #process the WORD ABOUT
        for i, p in enumerate(t['paragraphs'][wa_p:]):
            wap_text = joinSents(p['sents'])
            if 'A WORD ABOUT' in wap_text:
                #add the text before 'A WORD ABOUT' to the previous stop's excerpt
                to_prev = {'sents':[{'text':wap_text.split('A WORD ABOUT')[0]}]}
                appendNoEntPara(stops, to_prev)
                #add the rest to the footnotes list of paragraphs
                wap_text_rest = {'sents':[{'text':'A WORD ABOUT' + wap_text.split('A WORD ABOUT')[1]}]}
                wordabout.append(joinSents(wap_text_rest['sents']))
            else:
                wordabout.append(joinSents(p['sents']))
        #join all of the sents
        wa = lineBreaks(' '.join(wordabout), formatting=formatting)
        #create the stop for the word about the author
        stop = {}
        stop['title'] = 'A WORD ABOUT THE AUTHOR'
        stop['lead-in'] = wa[0:35] + '...'
        stop['excerpt'] = lineBreaks(wa.replace('Top of page', ''), formatting=formatting)
        stop['tour'] = 'Back matter'
        stops.append(stop.copy())


# ### Make final edits to stops
# Some stops are just references to other trees and not about the actual trees on the tour, so we should delete these. I compiled a list manually in the 'pp-tree-trails_deletes.json' file.

def stripMarkup(text):
    """Remove HTML and markdown markup from text"""
    text = text.replace('**', '').replace('_', '')
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

#open the manually created list of entries to delete
d = open('pp-tree-trails_deletes.json', 'r')
deletes = json.load(d)

#check the lead-in and species of each stop against the list of deletes and add to a new final_stops list if not in the deletes list
final_stops = []
for i, s in enumerate(stops):
    if not any((s['lead-in'] == d['lead-in']) and (s['species'] == d['species']) for d in deletes):
        final_stops.append(s)
    #if deleting the stop means deleting the only instance of the paragraph(s), then remove the formatting and 
    #add it to the previous stop
    else:
        if final_stops[-1]['lead-in'] != s['lead-in'] and stops[i+1]['lead-in'] != s['lead-in']:
            final_stops[-1]['excerpt'] = final_stops[-1]['excerpt'] + '\n' + stripMarkup(s['excerpt'])
            #if there is more than one stop with that lead-in, add it to all of them
            if len(final_stops) > 1:
                prev_stop = -2
                while final_stops[prev_stop]['lead-in'] ==  final_stops[-1]['lead-in']:
                    final_stops[prev_stop]['excerpt'] = final_stops[prev_stop]['excerpt'] + '\n' + stripMarkup(s['excerpt'])  
                    prev_stop = prev_stop - 1
        
#add sequence numbers in case the list needs to get resorted
seq = 1
for f in final_stops:
    f['sequence'] = seq
    seq += 1


# ### Write the final tour stop list out ot CSV

#write to CSV for import into app
stop_out = open('tree_trails.csv', 'w')
writeStopsToCsv(final_stops, stop_out)


# ### Reduce the tree species list to only those that appear in the guide and write to CSV

final_tree_species = []
sections = [t['paragraphs'] for k, t, in tours.items()]
for ts in tree_species:
    in_final = False
    for s in sections:
        for p in s:
            for k, m in p['merged_ents'].items():
                if ts['id'] == k:
                    if in_final == False:
                        final_tree_species.append(ts)
                        in_final = True
    

writeSpeciesToCsv(final_tree_species)


# ## Import data into Memento or Airtable
# Follow the steps in [importing-database-data.md](importing-database-data.md) to create the Memento or Airtable databases on your Android phone and import the data from 'tree_species.csv' and 'tree_trails.csv'
