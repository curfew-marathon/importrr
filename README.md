# importrr

importrr is a Python application designed to automate importing of image and movie files into a photo library.  It wraps around Phil Harvey's [ExifTool](https://exiftool.org/) which does the heavy lifting behind the scenes.  Following the DRY (don't repeat yourself) principle, the application follows the same steps to adjust and clean up the files before sorting and storing them in the photo library.  Once running the images only need to be copied into the import directories and they will be properly organized into the photo album.

# Configuration

The configuration file is read from <code>/config/config.ini</code>

File structure:

    [global]
      album_dir = /album
      archive_dir = /archive

    [folder1]
      import_dir = import1

    [folder2]
      import_dir = import2,import3

The <code>global</code> section outlines the root folders which apply to each of the sections.  The <code>[section]</code> will be appended to the root folders and the images will be pulled in from the <code>import_dir</code> directories.  The <code>import_dir</code> can support multiple values separated by a comma.

In the configuration above for <code>folder1</code>, the images will be imported from <code>/album/folder1/import</code>, renamed and sorted into <code>/album/folder1/yyyy/mm/yymmdd-hhmmss-c.ext</code> and a tar of the images placed in <code>/archive/folder1/yymmdd-hhmmss-c.tar</code>

For <code>folder2</code>, there will be two iterations.  In the first one, the images will be imported from <code>/album/folder2/import2</code>, renamed and sorted into <code>/album/folder2/yyyy/mm/yymmdd-hhmmss-c.ext</code> and a tar of the images placed in <code>/archive/folder2/yymmdd-hhmmss-c.tar</code>.  In the second one, the images will be imported from <code>/album/folder2/import3</code>, renamed and sorted into <code>/album/folder2/yyyy/mm/yymmdd-hhmmss-c.ext</code> and a tar of the images placed in <code>/archive/folder2/yymmdd-hhmmss-c.tar</code>.  Using multiple import directories is handy when importing images from multiple devices which could potentially have a naming collision.

Image files which cannot be cleaned, are corrupted or have malformed EXIF data will be left in a timestamped directory of <code>import_dir</code>.  Assuming the data can be manually fixed by the user, the image files can be placed back into the import directory for re-import.  

# Process

1. Find files in the <code>import_dir</code> which have not been accessed in the last 2 min
2. Move the files to a timestamped sub-folder
3. Adjust all the file extensions based on each file's MIME types
4. Update blank Exif DateTimeCreated if <code>CreateDate</code> is available
5. Update blank Exif DateTimeCreated if <code>FileModifyDate</code> is available
6. Sort the files into <code>yyyy/mm</code> folders and rename to <code>yyyymmdd-hhmmss-c.ext</code>
7. If specified, tar a copy of the images into chunks in the archive directory

# Docker

importrr comes with a simple Docker container to run the application.  It will require the configuration folder, preferably mounted as well as the image folders, also mounted.  The application runs in a <code>cron</code>job as usually the image files are stored on a network share and it's impossible to listen for file creation events.  

# Usage

Local:

<code>python3 launch.py</code>

Docker:

    cd importrr    
    docker build -t importrr .
    docker run importrr -d

# License

importrr is free software under the terms of the GNU General Public License.