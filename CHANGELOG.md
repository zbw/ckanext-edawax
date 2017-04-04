Changelog
=========

started with version 1.1.1

v1.3.0
------
[not yet released]

-   Packages and resources cannot be deleted if they have a DOI assigned
-   Package cannot be retracted if DOI assigned
-   All above features also go for DOI_Test. In that case only sysadmins still can
    delete or retract.
-   add favicon
-   implement /jdainfo as git-submodule (and remove old git-subtree)
-   also display DOI in package view if it is just a DOI_Test



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
