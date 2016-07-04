# ckanext-edawax
CKAN extension for [ZBW Journaldata Archive](http://journaldata.zbw.eu). Provides
modifications of route and link naming (organizations => journals) as well as some theming
and layout modifications. Also implements a workflow for journals.

This package has been developed for the [EDaWaX](http://http://www.edawax.de/) project at
the [ZBW](http://zbw.eu) (German National Library of Economics).


## Requirements
tested with CKAN 2.4

**Note**:
for several reasons the workflow implementation does not work with the original CKAN.
Minor modifications are necessary to make it work. If you're interested in that you must
use the fork at https://github.com/hbunke/ckan/tree/edawax-v2.4.1/ckan


## Installation
Clone this repository into your CKAN src folder and install it the usual way `pip install
-e path/to/repo` or `python setup.py` inside your virtualenv.

## Main Features
-   Naming adapted to Journal purposes: Organizations ==> Journals, 'Members' ==> Authors

-   Workflow for Journals
    -   Journaleditor adds Author
    -   Author get's email with URL
    -   Author uploads dataset, Dataset is private
    -   Author sets clicks 'Send to review', Editor get's email, Dataset state is 'review'
    -   Journaleditor adds some metadata and publishes Dataset.

## License
This extension is open and licensed under the GNU General Public License (GPL)
v3.0. Its full text may be found at: http://www.gnu.org/licenses/gpl.html

## Contact
Please use GitHub issues for filing any bug or problem. If you have further questions
please contact h.bunke@zbw.eu.
