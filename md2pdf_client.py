#!/usr/bin/env python3
'''
md2pdf_client: A client application to render a Markdown file into a PDF via a
connection to an md2pdf server.
Copyright (C) 2018  Sean Lanigan, Extel Technologies

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
'''

global __version__
__version__ = "1.0.2"

import argparse
import requests
import time
import re
import os
import shutil
import sys
import glob
import tempfile
import logging
from ruamel.yaml import YAML

yaml = YAML()

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)-7s: %(message)s'
                    )

def main():
    ## Hard-coded defaults, used if no config file exists
    def_server = "127.0.0.1:9090"
    def_proto = "http"

    ## Read the config file, or create it if it doesn't exist
    # Try and see if we are running as an Ubuntu Snap package
    try:
        config_path = os.environ["SNAP_USER_COMMON"]
        config_path = os.path.join(config_path, "md2pdf.yaml")
    except (KeyError):
        # This would fail on a 'normal' Linux install, so use ~/ instead
        config_path = os.path.expanduser("~")
        config_path = os.path.join(config_path, ".md2pdf.yaml")

    # Try to open the file, if it exists
    have_config = False
    try:
        config_file = open(config_path, 'rt', encoding="utf-8")
        have_config = True
    except (FileNotFoundError):
        logging.warning("Config file not found at '%s', will create one with defaults", config_path)

    if not have_config:
        # Create a file with default values in it
        config_file = open(config_path, 'wt', encoding="utf-8")
        conf = {}
        conf["server"] = def_server
        conf["proto"] = def_proto
        yaml.dump(conf, config_file)
        # Write out the file, then read from it again
        config_file.close()
        config_file = open(config_path, 'rt', encoding="utf-8")

    conf = yaml.load(config_file)
    config_file.close()

    def_server = conf["server"]
    def_proto = conf["proto"]


    ## Parse the command-line arguments
    parser = argparse.ArgumentParser(description='md2pdf client v' + __version__ + ' - connect to an md2pdf server and create a PDF file')
    parser.add_argument('file', nargs="?", metavar=("FILEPATH"), help="Input Markdown file to be converted")
    parser.add_argument('-c', '--compare', nargs=1, metavar=("FILEPATH"), help="Activates 'compare' mode. Specify the file to compare changes with, e.g.: 'md2pdf-client --compare path/file-old.md path/file-new.md'")
    parser.add_argument('--set-default', nargs=2, metavar=("OPTION", "VALUE"), help="Change a default value for an option. Use the full argument name, separated by a space, e.g.: '--set-default proto https' or '--set-default server 192.168.1.1:9090'")
    parser.add_argument('-s', '--server', metavar=("ADDRESS[:PORT]"), help="Server address to request PDF generation from. Use hostname or IP address, and port number if required (i.e. '127.0.0.1:9090', or 'my-host.com:8888'). If port is not specified, port 80 will be used", default=def_server)
    parser.add_argument('--proto', help="Protocol to use", default=def_proto, choices=["http", "https"])
    parser.add_argument('-t', '--template', metavar=("TEMPLATE"), help="Template to use, instead of the server default (include the file extension)")

    args = parser.parse_args()


    ## Set new defaults, if command is given
    if args.set_default:
        if args.set_default[0] not in {"server", "proto"}:
            logging.critical("Invalid default setting '%s'", args.set_default[0])
            return -1
        # Save new config file
        with open(config_path, 'wt', encoding="utf-8") as config_file:
            logging.info("Setting default %s value to '%s'", args.set_default[0], args.set_default[1])
            conf[args.set_default[0]] = args.set_default[1]
            yaml.dump(conf, config_file)
            return 0


    ## If file has not been given, exit at this point
    if not args.file:
        logging.critical("Input file not given. Use -h flag for help.")
        return -2

    filename = os.path.abspath(args.file)
    server_address = args.server
    proto_string = args.proto

    ## Check for compare mode
    if args.compare:
        # Compare mode
        compare_filename = os.path.abspath(args.compare[0])
        logging.info("Starting md2pdf client in compare mode, showing changes from '%s' to '%s'", compare_filename, filename)
        output_zip_filename = createZipCompareMode(compare_filename, filename)
    else:
        # Normal mode
        logging.info("Starting md2pdf client, with input file '%s'", filename)
        output_zip_filename = createZipNormalMode(filename)

    # Ensure output_zip_filename is a string
    if not isinstance(output_zip_filename, str):
        logging.critical("The output ZIP path does not seem to be correct")
        raise TypeError("ZIP path is not a string")

    ## Upload the ZIP file to the md2pdf-server address
    headers = {'x-method': 'MD-to-PDF'}
    if args.template:
        logging.info("Using template override '%s'", args.template)
        headers['x-latex-template'] = args.template
        logging.debug(headers)
    url = proto_string + "://" + server_address + "/upload"
    files = {'ufile': open(output_zip_filename, 'rb')}

    try:
        send = requests.post(url, headers=headers, files=files)
        status_code = send.status_code
        logging.info("Response from server: %s", send.text)
    except requests.exceptions.ConnectionError as err:
        logging.error("Server connection error - %s" % err)
        status_code = -3


    ## Request the PDF from the server
    if(status_code == 200):
        hashsum = send.cookies['hashsum']

        get_string = proto_string + "://" + server_address + "/fetch?hashsum=" + hashsum

        # Try several times to get the file, pausing in between
        attempts = 4
        have_pdf = False

        logging.info("Will wait 7 seconds then try to download PDF")

        # Remove the ZIP archive
        os.remove(output_zip_filename)

        while attempts > 0:
            time.sleep(7)
            receive = requests.get(get_string)

            if(receive.status_code == 200):
                receive_name = re.findall("filename=\"(.+)\"", receive.headers['content-disposition'])[0]

                # Write file to disk, using the name from the content header
                with open(receive_name, 'wb') as fd:
                    for chunk in receive.iter_content(chunk_size=512):
                        fd.write(chunk)

                # Check if the received file was a PDF
                if receive_name.find(".pdf") > -1:
                    # Stop now that we have a PDF file
                    attempts = 0
                    have_pdf = True
                    last_file = receive_name
                else:
                    # Decrement and try again
                    attempts = attempts - 1
                    logging.info("Did not receive a PDF file yet, will try again in 7 seconds")
                    if attempts == 0:
                        last_file = receive_name

            else:
                logging.debug(receive)
                logging.debug(receive.text)
                # Stop trying to get the PDF
                attempts = 0
                logging.error("An error occurred, the PDF was not received")

        if have_pdf:
            logging.info("Successfully received PDF file: " + last_file)
            return 0
        else:
            print("Unable to receive PDF file, check log for more information: " + last_file)
            input("\nPress enter to close ")
            return -4

    else:
        if status_code == -3:
            print("Failed to connect to server - check the server address is configured correctly")
        else:
            print("Error when sending to server")
            print("Server response: %s" % send)
        input("\nPress enter to close ")
        return -5
# end main()

def createZipArchive(input_directory, output_name):
    'Helper function to create a ZIP archive'
    ## Create ZIP of input directory
    shutil.make_archive(output_name, "zip", input_directory)
    output_name += ".zip"
    logging.info("Created ZIP archive '%s'", output_name)

    return output_name
# end createZipArchive()

def createZipNormalMode(input_md):
    'Helper function to take an input file and produce a ZIP archive'
    # cd into the folder that contains the file
    os.chdir(os.path.dirname(input_md))

    ## Check that the given file is a text file
    try:
        in_file = open(input_md, 'rt', encoding="utf-8")
    except (OSError):
        logging.critical("Could not open file %s", input_md)
        raise

    with tempfile.TemporaryDirectory() as tmpdirname:
        logging.debug("Created temporary directory '%s'", tmpdirname)

        # Create "images" subfolder
        base_filename = os.path.split(input_md)[1]
        first_word = re.search("(\w*)", base_filename)
        base_image_dirname = first_word.group(1)+"_images"
        images_filepath = os.path.join(tmpdirname, base_image_dirname)

        if not os.path.exists(images_filepath):
            os.makedirs(images_filepath)
        ## Read input file and sanitise if necessary into a local string object
        sanitised_file_str = ""
        ## Check if MD file has reference to any images
        # Look for regex pattern \!\[.*?\]\s*?\(.*?\)
        image_pattern = re.compile("\!\[.*?\]\s*?\((.*?)\)")
        for line in in_file:
            # Check if images need sanitising
            image_match_original = image_pattern.search(line)
            if image_match_original:
                # Update the sanitised version if necessary
                # Check for the location of the image
                image_filename = os.path.split(image_match_original.group(1))[1]
                logging.info("Looking for image file '%s'", image_filename)

                # Copy images to temporary directory
                image_found = False
                for root, dirs, files in os.walk("./"):
                    for file in files:
                        if file.endswith(image_filename):
                            copy_filename = os.path.join(root, file)
                            # Copy image to temporary directory
                            logging.info("Found image file: '%s'", copy_filename)
                            shutil.copy(copy_filename, images_filepath)
                            dest_filename = os.path.join(base_image_dirname, file)
                            dest_filename = os.path.join(".", dest_filename)
                            logging.debug("New path to image is '%s', updating MD file", dest_filename)
                            image_found = True
                            new_line = line.replace(image_match_original.group(1), dest_filename)
                            sanitised_file_str += new_line
                            break # Only copy first found image
                if not image_found:
                    logging.error("Image not found: '%s'. PDF generation will probably fail", image_filename)
            else:
                # Copy across the line as-is
                sanitised_file_str += line

        ## Write sanitised file to disk
        sanitised_filename = os.path.join(tmpdirname, base_filename)
        logging.debug("Writing sanitised MD file to '%s'", sanitised_filename)
        with open(sanitised_filename, 'w', encoding="utf-8") as sanitised_file:
            print(sanitised_file_str, file=sanitised_file)

        ## Create ZIP of MD file, and any images if required
        zip_name = os.path.join(os.getcwd(), os.path.splitext(base_filename)[0])
        output_zip_filename = createZipArchive(tmpdirname, zip_name)
    # tmpdirname will be deleted now

    return output_zip_filename
# end createZipNormalMode()

def createZipCompareMode(input_md_old, input_md_new):
    'Helper function to take two input files and produce a ZIP archive'
    # cd into the folder that contains the file
    os.chdir(os.path.dirname(input_md_new))

    with tempfile.TemporaryDirectory() as tmpdirname:
        logging.debug("Created temporary directory '%s'", tmpdirname)

        for (input_md, input_type) in ((input_md_old, "old"), (input_md_new, "new")):
            base_filename = os.path.split(input_md)[1]
            try:
                with open(input_md, 'rt', encoding="utf-8") as in_file:
                    logging.debug("Replacing images in file '%s'", input_md)
                    ## Read input file and sanitise if necessary into a local string object
                    sanitised_file_str = ""
                    ## Check if MD file has reference to any images, replace them with an fbox
                    # Look for regex pattern \!\[(.*?)\]\s*?\(.*?\)\s?(?:{.*?})?
                    image_remove_pattern = re.compile("\!\[(.*?)\]\s*?\(.*?\)\s?(?:{.*?})?")
                    for line in in_file:
                        # Check if images need removing
                        re_match = image_remove_pattern.search(line)
                        if re_match:
                            # Format the replacement string
                            new_line =  "\\fbox{\\textbf{IMAGE:} " \
                                        + re_match.group(1) \
                                        + "}"
                            # Insert the replacement
                            new_line = line.replace(re_match.group(0), new_line)
                            sanitised_file_str += new_line
                        else:
                            # Keep the line as-is
                            sanitised_file_str += line

                    ## Write sanitised file to disk
                    new_name = base_filename.replace("md", input_type + ".md")
                    sanitised_filename = os.path.join(tmpdirname, new_name)
                    logging.debug("Writing sanitised MD file to '%s'", sanitised_filename)
                    with open(sanitised_filename, 'w', encoding="utf-8") as sanitised_file:
                        print(sanitised_file_str, file=sanitised_file)

            except (OSError):
                logging.critical("Could not open file %s", input_md)
                raise

        ## Create ZIP of MD files
        zip_name = os.path.join(os.getcwd(), os.path.splitext(base_filename)[0])
        output_zip_filename = createZipArchive(tmpdirname, zip_name)
    # tmpdirname will be deleted now

    return output_zip_filename
# end createZipCompareMode()

if __name__ == '__main__':
    main()
