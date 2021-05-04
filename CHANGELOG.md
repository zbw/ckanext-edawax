Changelog
=========

started with version 1.1.1

v2.0.0
------
[2021-03-03]
-   Migrate from Pylons to Flask for CKAN 2.9


v1.3.9
------
[2020-07-29]
-   Add modal for related publication check when publishing
-   Update to metadata in resources
-   Allow links in 'info' boxes
-   Update to how related publications are displayed
-   Add reviewer role

v1.3.8
------
[2020-02-27]
-   Hide 'social' box until published
-   Add notification when journaleditor tries to publish a dataset with no "related" publication
-   Update to user files
-   Add 'back to datset' button to resources
-   Improve breadcrumb creation
-   Use Crossref to improve "related publication" when a DOI is present
-   Updates to invitation and notification emails

v1.3.7
------
[2019-11-20]
-   Update to emails
    -   Add notification email to author when dataset is published or retracted
    -   Add salutations to emails
-   Redesign of JDA updates to HTML and CSS
-   Adjustments to work with SSL
-   Prevent author from editing once dataset sent to editor
-   Update user documentation
-   

v1.3.6
------
[2019-06-25]
-   Update user manual
-   Add robot check to download all
-   Add citation to "download all"
-   Adjust citation creation to account for special characters
-   Fix Chrome not being able to download all if there are commas in file names
-   Fix template used for sorting displaying unwanted text
-   Add guidance for using CKAN API
-   Add ability to export citations as RIS or BibTex
-   Update license deposit message
-   Handle 'null' values in dara_authors
-   


v1.3.5
------
[2019-03-25]
-   Update how tracking is handled
-   Allow authors to delete resources they added for unpublished datasets
-   Prevent additions to a dataset if a DOI has been registered
-   Update "download all"
    -   now works with private datasets
    -   won't appear if there is one resource and one URL
    -   Fix special characters in journal titles causing this to fail
-   Move "cancel" button to 'dara' extension
-   Fix ascii appearing in URLs
-   Add "Private" to order by on results pages for journaladmins
-   Update to citation display


v1.3.4
------
[2019-01-25]
-   Update style for breadcrumbs
-   Update documentations: user manual, leaflet
-   Account for datasets with no resources, and "unnamed" resources
-   Resources that are only URLs now link to external site
-   Adjust location of popup statistics to account for very long titles
-   Add scroll wheel for popup statistics with many resources
-   Try to identify robots based on user agent

v1.3.3
------
[2018-11-29]
-   Add ability to "download all" resource if there is more than one for a dataset
-   Update data privacy information
-   Update to css to fix issue in Firefox
-   Add recent and total counts for journal visits
-   Add popover to show datasets statics from dataset list


v1.3.2
------
[2018-09-28]
-   Fix preview page reloading not loading when pressing "preview"
-   Fix "download" button not showing for files that couldn't be previewed
-   Update contact and imprint information
-   Updates to invitation emails
    -   Add different email notifications depending on the role
    -   Add ability to include attachements to email invitations
    -   Format, subject updates


v1.3.1
------

-   add re3data.org badge
-   new manuals
-   integrate jdainfo
-   FIX: journaladmin could not publish if she's owner
-   FIX: only show TEST DOI when config has use_testserver


v1.3.0
------

-   Packages and resources cannot be deleted if they have a DOI assigned
-   Package cannot be retracted if DOI assigned
-   All above features also go for DOI_Test. In that case only sysadmins still can
    delete or retract.
-   add favicon
-   implement /jdainfo as git-submodule (and remove old git-subtree)
-   Display DOI in package view even if it is just a DOI_Test
-   Implement DIW/SOEP logo in footer
-   change background of footer, and color of footer sitelinks



v1.2.1
------
**2017-02-02**

-   Update user manuals


v1.2.0
------
**2017-02-02**

-   improved workflow: editors can send back dataset to author and request
    revision. (#1)

-   Authors only have write permission if dataset is private (e.g. not
    published) AND not in review. Before authors could edit anyways, regardless
    of dataset state.

-   refactoring of journals index.


v1.1.1
------
**2017-01-18**

-   implement article submission ID

-   redirect URLs for manuals

-   minor text modifications
