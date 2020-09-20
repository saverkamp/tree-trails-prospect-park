# tree-trails-prospect-park

__Tree Trails in Prospect Park__, by George Kalmbacher and M. M. Graff, published by Greensward Foundation, was a 1968 book of four walking tours through Brooklyn's Prospect Park. The book is [freely available](https://www.echonyc.com/~parks/books/treetrailsppk.html) on the Greensward Foundation website, and while the text paints a vivid picture of the varied landscape of Prospect Park, sometimes actual pictures are helpful for beginners just starting their journey in tree identification. 

[This notebook](https://github.com/saverkamp/tree-trails-prospect-park/tree_trails_prospect_park.ipynb) walks you through the process of using linked data (with [Wikidata](https://www.wikidata.org)) and natural language processing (with [SpaCy](https://spacy.io/)) to enrich a 1968 book of walking tours of Prospect Park trees with images and species information for easier identification. It outputs two CSV files suitable for import into two linked [Memento](https://mementodatabase.com/) databases (Android or desktop only). One database will contain information on the tree species (taxon name, common names, links to Wikipedia, Wikimedia Commons for images, and iNaturalist) and the other will contain the stops on the tours linked to the trees featured, with editable fields for you to store your location when you find the tree and any photos you take. Alternatively, you can output two CSV files to create an [Airtable](https://airtable.com/) database (change `formatting` variable to 'airtable' under the "Generating tour stops..." block), though setup is a little more involved and Airtable does not support a geographic coordinates datatype, so you will not be able to store your location. It also doesn't support rich text for data imported through CSV, so you won't see tree species highlighted in the text.  

This process is broken out into the following stages:  

- Get a list of all possible tree species and related information from Wikipedia and Wikidata
- Use the SpaCy natural language programming library to locate instances of these trees in the text - Reshape the text of the book with the tree information as an interactive database  

You will need to install the following Python libraries (all available with pip):  

- requests
- lxml
- jsonlines
- spacy  

If you want to skip directly to installing and loading the [data](https://github.com/saverkamp/tree-trails-prospect-park/data), follow the instructions in [importing-database-data.md](importing-database-data.md).
