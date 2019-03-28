<!--
This file is part of the IDA research data storage service

Copyright (C) 2018 Ministry of Education and Culture, Finland

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

@author CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
@license GNU Affero General Public License, version 3
@link https://research.csc.fi/
-->

# IDA Command Line Tools

This repository provides a [bash](https://www.gnu.org/software/bash/) script `ida` for interacting with
v2 of the [IDA service](https://www.fairdata.fi/en/ida/) from the command line. Examples are provided at
the end of this guide.

    Usage: ida [-h]
           ida upload   [-v] [-c config] [-i ignore] [-t host] [-p project]    target_pathname local_pathname
           ida download [-v] [-c config]             [-t host] [-p project] -f target_pathname local_pathname
           ida move     [-v] [-c config]             [-t host] [-p project]    target_pathname new_target_pathname
           ida delete   [-v] [-c config]             [-t host] [-p project]    target_pathname
           ida info     [-v] [-c config]             [-t host] [-p project] -f target_pathname
    
           -h : show this guide
           -v : provide verbose output
           -c : configuration file
           -i : ignore file
           -t : target host (default: "https://ida.fairdata.fi")
           -p : project name
           -f : service pathnames are relative to frozen area


Pathnames may correspond to either files or folders. If a folder is specified, then the action is
performed for all files within that folder and all subfolders. Folders are downloaded as zip files.
Actions can be performed on only one file or folder at a time.

Unless the -f parameter is specified, `target_pathname` and `new_target_pathname` are relative to the
staging area of the specified project. If the -f parameter is specified for either a download or
info action, then `target_pathname` and `new_target_pathname` are relative to the frozen area of the
specified project. The -f parameter is **only** allowed for download and info actions.

`local_pathname` is the pathname of a folder or file on the local system which is to be uploaded, or the
pathname on the local system to which a file will be downloaded (either a single data file or the zip
file for a data folder). Existing files will not be overwritten.

`move` can also be used to rename a file or folder without changing its location.

## Installation

Download the `ida` script, ideally placing it in a location somewhere in your `$PATH`, and ensure that
the script is executable:

    chmod +x ida
    
The `ida` script requires that `bash` is installed on your system as `/bin/bash` and that `curl` is installed
on your system somewhere in your `$PATH`.

## Configuration

The `ida` script requires that certain parameters are defined,
either via environment variables or provided as arguments.

### Configuration file

The `ida` script will look for and load a file `.ida-config` if it exists in your home directory.

You can copy the provided example `ida-config` file from the `templates` subdirectory to your home directory
as `.ida-config` and edit it accordingly.

It is also possible to explicitly specify a configuration file using the `-c` command line option.

Configuration settings will be taken from existing environment variables, followed by `$HOME/.ida-config`,
followed by a configuration file specified with the `-c` command line option, followed by any other
specified command line options; thus, it is possible to partially or completely override configuration
settings defined at each subsequent level of specification.

### Project

You may define the name of your project using the `IDA_PROJECT` environment variable.

    IDA_PROJECT="myproject"
    
You may also specify the project using the `-p` command line option.

If you belong to more than one project, you can define 
whichever project is most frequently used and use the `-p` commmand line option to
explicitly specify another project when different from the default.

All target pathnames are considered to be relative to the staging or frozen area of the specified project.

### IDA Host

The `IDA_HOST` environment variable may be defined as something other than the main
production service, when appropriate. If undefined, the script will default to the 
main production service.

    IDA_HOST="https://ida.fairdata.fi"
            
## Authentication

The `ida` script will need to be provided your IDA account credentials in order to access the project space.

The username and password credentials are the same as you use to log in to the IDA web UI, and are managed in
the [SUI CSC Customer Portal](https://sui.csc.fi/).

Account credentials should ideally be defined using [netrc](https://ec.haxx.se/usingcurl-netrc.html).

You can copy the provided example `netrc` file from the `templates` subdirectory to your home directory
as `.ida-config` and edit it accordingly. Be sure to set the permissions of your netrc file securely:

    chmod go-rwx $HOME/.netrc
    
If a `.netrc` file exists in your home directory, the script will retrieve your credentials from there. 
If no `.netrc` file exists in your home directory, you will be prompted to enter your credentials on each invocation.

### App passwords

If you prefer not to use or store your personal account password, it is possible to create an application
specific password which can be used and stored in place of your official account password.

To create an app password, log in to the IDA web UI, and open the settings view by selecting "Personal" from
the pull down settings menu at the top right of the view, and then either select the "Security" section in the
left hand navigation pane or scroll down to the security section.

In the field provided, enter a name for your new app password and click "Create new app password". The new app
password will be displayed, and must be copied and saved immediately. It will not be possible to view the app
password again, though it will be listed by the provided name and you will be able to delete it and remove it 
from use.

Enter or store the app password in your .netrc file, the same as you would your official personal account password.

## Ignore file

The `ida` script will look for and use a file `.ida-ignore` if it exists in your home directory, to exclude
files matching certain patterns from upload.

This is useful when uploading entire folders, to exclude special system files such as `.DS_Store` on OS-X or
various temporary or log files which might exist within the local filesystem but are not part of the data to
be stored in IDA.

You can copy the provided example `ida-ignore` file from the `templates` subdirectory to your home directory
as `.ida-ignore` and edit it accordingly.

It is also possible to explicitly specify an ignore file using the `-i` command line option.

The ignore file should contain one pattern per line, and will be applied only to filenames, not to pathnames
or portions of pathnames. Patterns should be compatible with those understood by the `-name` option of the
POSIX `find` command.

## Collision Avoidance for File Operations
 
All users belonging to a given project have the same rights, and may interact with, add, and remove
project data concurrently. To help avoid one user unintentionally interfering with another user's
activity, the IDA service employs a number of checks and restrictions to ensure that multiple concurrent
users' activities do not collide in undesirable ways. 
 
Operations on files in the staging area, including uploading, deleting, renaming, and moving (but not
downloading), will not be allowed if they intersect with the scope of an action that is being initiated.

If an action is initiated in the web UI of the service, it takes precidence over any batch operations
utilizing the command line tools, such that the batch operations may be blocked by the initiated action.
In such cases, the command line tools will exit with an error message.

More details can be found in the [online user guide](https://www.fairdata.fi/en/ida/user-guide#collision-avoidance).

## Info and Listing Output

The output of the `info` action is both human friendly as well as easily parsable by script. 

### File Info

File info consists of a sequence of field::value pairs, one per line, with the field name
followed by a colon ":" and padded by one or more spaces. E.g.

    project:    12345
    pathname:   /2017-08/Experiment_1/test01.dat
    area:       frozen
    type:       file
    pid:        5c41b5d90561a361661419f75150
    size:       446
    checksum:   56293a80e0394d252e995f2debccea8223e4b5b2b150bee212729b3b39ac4d46
    encoding:   application/octet-stream
    modified:   2017-01-03T19:27:42Z
    frozen:     2017-01-18T11:17:15Z

Fields included for all files, in either the staging or frozen areas:

* project
* pathname
* area
* type
* size
* encoding
* modified
    
Additional fields provided for all files in the frozen area, if values exist:

* pid
* checksum
* frozen

Note: If the info for a file in the frozen area does not include a "checksum" field, it means
that postprocessing is still ongoing for the freeze action with which the file is associated.
Check the pending actions section of the IDA service web UI to monitor the status of pending actions.

### Folder Info

Folder info consists of a sequence of field::value pairs, one per line, with the field name followed
by a colon ":" and padded by one or more spaces. Field::value pair lines are
followed by a heading "contents:" on its own line, followed
by zero or more pathnames, one per line, corresponding to the files or folders contained within the specified
folder. E.g.

    project:    12345
    pathname:   /2017-08/Experiment_2
    area:       staging
    type:       folder
    size:       23040
    contents:
      /2017-08/Experiment_1/baseline/
      /2017-08/Experiment_1/test01.dat
      /2017-08/Experiment_1/test02.dat
      /2017-08/Experiment_1/test03.dat
      /2017-08/Experiment_1/test04.dat
      /2017-08/Experiment_1/test05.dat

Each pathname is indented with whitespace, and thereby easily distinguished from lines with field::value pairs,
where the field name begins at the start of each line.

Folder pathnames end in a forward slash "/", and thereby easily distinguished from file pathnames, which never
end in a forward slash.

Empty folders will have no output lines following the "contents:" heading.

To retrieve a listing of the root contents of either the staging or frozen area for a project, the target
pathname "/" can be specified.

Fields included for all folders, in either the staging or frozen areas:

* project
* pathname
* area
* type
* size
* contents

## Local File Checksum Generation

The included utility `ida-checksum` can be used to generate a checksum for a local file, of the same
format (SHA256, lowercase) used by the IDA service.

    Usage: ida-checksum -h
           ida-checksum local_pathname

## Special Notes

Files named `.htaccess` and files with a suffix of either `.part` or `.filepart` may not be uploaded.
The filenames will need to be changed in some manner, such as zipping the file or adding some other
suffix or name change. These restrictions are due to security and other internal management contraints
of the underlying Nextcloud platform employed by the IDA service.

Note that files are not officially stored persistently in the IDA service
until they are [frozen](https://www.fairdata.fi/en/ida/user-guide/#project-data-storage),
which can only be done using the web UI of the service.

## Examples

For the following examples, it is assumed that the user has defined their primary project in their
`.ida-config` file and their account credentials in their `.netrc` file.
Note that when uploading or moving files or folders, complete target pathnames in the project staging area must
always be specified, not merely the pathname of the folder into which data will be uploaded or moved.

**Upload a local folder named "run42" to the staging area with the relative pathname "/2017-04/Experiment_42":**

    ida upload /2017-04/Experiment_42 run42
    
**Upload a local file named "run42/test66.dat" to the staging area with the relative pathname "/2017-04/Experiment_42/test66.dat":**

    ida upload /2017-04/Experiment_42/test66.dat run42/test66.dat
    
**Download a folder from the staging area with the relative pathname "/2017-04/Experiment_42" to the local file "run42.zip":**

    ida download /2017-04/Experiment_42 run42.zip
    
**Download a folder from the frozen area with the relative pathname "/2017-04/Experiment_42" to the local file "run42.zip":**

    ida download -f /2017-04/Experiment_42 run42.zip
    
**Download a file from the staging area with the relative pathname "/2017-04/Experiment_42/test66.dat" to the local pathname "run42/test66.dat":**

    ida download /2017-04/Experiment_42/test66.dat run42/test66.dat
    
**Download a file from the frozen area with the relative pathname "/2017-04/Experiment_42/test66.dat" to the local pathname "run42/test66.dat":**

    ida download -f /2017-04/Experiment_42/test66.dat run42/test66.dat
    
**Rename (move) a folder in the staging area from "/2017-04/Experiment_42" to "/2017-04/Experiment_42a":**

    ida move /2017-04/Experiment_42 /2017-04/Experiment_42a
    
**Move a file in the staging area from "/2017-04/Experiment_42/test66.dat" to "/2017-04/Experiment_42/verified/test66.dat":**

    ida move /2017-04/Experiment_42/test66.dat /2017-04/Experiment_42/verified/test66.dat
    
&nbsp;&nbsp;&nbsp;&nbsp;The folder "/2017-04/Experiment_42/verified" will be created if it does not already exist.
    
**Delete a folder from the staging area with the relative pathname "/2017-04/Experiment_42":**

    ida delete /2017-04/Experiment_42
    
**Delete a file from the staging area with the relative pathname "/2017-04/Experiment_42/test66.dat":**

    ida delete /2017-04/Experiment_42/test66.dat
    
**Retrieve info about a folder in the staging area with the relative pathname "/2017-04/Experiment_42":**

    ida info /2017-04/Experiment_42
    
**Retrieve info about a folder in the frozen area with the relative pathname "/2017-04/Experiment_42":**

    ida info -f /2017-04/Experiment_42
    
**Retrieve info about a file in the staging area with the relative pathname "/2017-04/Experiment_42/test66.dat":**

    ida info /2017-04/Experiment_42/test66.dat
    
**Retrieve info about a file in the frozen area with the relative pathname "/2017-04/Experiment_42/test66.dat":**

    ida info -f /2017-04/Experiment_42/test66.dat
    
**Retrive info about the root of the staging area of the project:**

    ida info /
    
**Retrive info about the root of the frozen area of the project:**

    ida info -f /
    
