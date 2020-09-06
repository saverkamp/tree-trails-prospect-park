# Importing data into Memento or Airtable

## Importing data into Memento
Before starting you should have ready the two datasets for import, tree_species.csv and tree_trails.csv.  

Memento is available for Android (or desktop) only, but if you are using an iPhone, there may be a similar database app for which these datasets will work.  

### Download and install Memento if you haven't yet already.
- [Android](https://play.google.com/store/apps/details?id=com.luckydroid.droidbase&hl=en_US)
- [Desktop](https://mementodatabase.com/)

### Create the Memento libraries
Download the template schemas for Tree Trails in Prospect Park by going to the Memento home screen, select "Catalog templates" from the upper left navigation, then search for "Tree Trails in Prospect Park." Select the download option in the lower right. This will also download the Tree species library template.

### Import the data
- Download the tree_species.csv and tree_trails.csv files to an accessible location on your phone (Downloads folder will work just fine.)
- From the Memento home screen, click into the "Tree species" library. In the upper right options, select the options icon to the right of "Edit library" and select "Import and export >"
Select "Import from CSV" and navigate to the "tree_species.csv" file on your phone. Make sure "Field delimiter" is set to "," and "Text qualifier" is set to " and select "IMPORT".
- Return to the Memento home screen and follow the previous instruction for the "Tree trails" library, importing the "tree_trails.csv" file.   

### Using the app
You can now use the "Tree trails" library to follow tours and document the trees you find. 
- Filter on specific tours by swiping left and selecting "Filters".
- For each entry, clicking on the "Tree species" field will take you to the corresponding entry in the "Tree species" library, which contains links to the tree's Wikipedia page, images in Wikimedia Commons, and its iNaturalist page, all of which can help you to identify the tree listed in the tour stop.
- In each entry, you can click the edit icon in the upper right to use Google Maps to add the geographic coordinates of the tree (defaults to current location), add images, indicate the status of the tree--Living, Dead, or Can't locate--or add any notes.
- Once you've added locations to your data, you can view the tour as a map by swiping left from the tour stop list and selecting "View" > "Map". You can also view as cards or as a table.  

## Importing data into Airtable
Before starting you should have ready the two datasets for import, tree_species.csv and tree_trails.csv.   

### Download and install Airtable if you haven't yet already.

- [Website](https://airtable.com/)
- [Android](https://play.google.com/store/apps/details?id=com.formagrid.airtable)  
- [iPhone](https://apps.apple.com/us/app/airtable/id914172636)  

You will probably find it easier to create the database on the desktop version and then sync it on your phone.

### Create a new Airtable base
- In an existing Workspace or a new Workspace, select "Add a base"
- Select "Import a spreadsheet"
- Select "CSV file"
- Add the tree_species.csv file to the upload canvas
- Rename your base to whatever you like and rename the Imported Table to "Tree species"
- Click to add a tab next to the Tree species table tab and select "Import a spreadsheet". Upload the "tree_trails.csv" file and rename the tab "Tour stops"
- You'll need to change the datatypes of some of the fields and link the two tables. Use the table below as a guide. (Change datatypes by selecting the dropdown menu of each column and then choosing "Customize field type")  

**Tree Species**
| Column            | Field type       |
|-------------------|------------------|
| Species           | Single line text |
| Common names      | Long text        |
| Wikipedia         | URL              |
| Wikimedia Commons | URL              |
| iNaturalist       | URL              |  

**Tour Stops**
| Column       | Field type                                                                                                                                                                    |
|--------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Name         | Single line text                                                                                                                                                              |
| Description  | Long text                                                                                                                                                                     |
| Excerpt      | Long text                                                                                                                                                                     |
| Tree species | Link to another record > Tree species > Allow linking to mulitple records (Under "Add lookup fields" select whichever you like. These will appear in the Tour stops entries.) |
| Tour         | Single line text                                                                                                                                                              |
| Sequence     | Number (format = Integer)                                                                                                                                                     |  

You can also add fields for your own notes, photos, and tracking tree status:
| Column | Field type                                                  |
|--------|-------------------------------------------------------------|
| Status | Single select (add options for "Unknown", "Living", "Dead") |
| Photos | Attachment                                                  |
| Notes  | Long text                                                   |  

### Adding filters (optional)
If you want to apply tour filters, so you can view just a single tour at once, you can add filters for each:
- Select the Filters option in the top nav and click at add a filter
- First rename your current View as the default view by right-clicking and renaming "Grid 1" in the top nav to "All entries"
- Under "Add view" in the lower left sidebar, select "Grid" to add a new view and select it (checkmark should appear next to it)
- Add a filter similar to this: "Where Tour is TOUR 1"
- Rename the view as you did above with the name of the tour
- Repeat the process of creating a view, adding a filter, and renaming the view for each tour
