# md2pdf Client

![md2pdf icon](icon.svg)

## Introduction

md2pdf is a little project that aims to make it easy to produce
professional-looking PDF documents from Markdown files via a LaTeX template and
the help of Pandoc.

There are several motivations for this:

- Word processor software does not work very nicely with version control, plain-text Markdown files do
- Collaborating on a single ODT/DOC file is prone to overwriting others' work
- LibreOffice and Word both suck with automatic figure and table numbering on long files, and with TOCs etc
- It's painful trying to keep everyone using the right font, spacing, formatting, etc. when collaborating with ODT/DOC files
- PDF output from LibreOffice and Word often looks pretty average
- It's distracting having to worry about formatting while writing - Markdown takes away all but the most basic formatting options to focus you on writing


With with an appropriate template, LaTeX PDF output is undeniably the prettiest-
looking way to create documents. But, learning LaTeX is hard. Markdown
is much easier to use, and when used with Pandoc can still produce superb PDF
documents. md2pdf makes it simple to manage having the right LaTeX templates and
configuration across a whole team, by using a central server to do the PDF
generation and then share the result with those who need it.


## Client application

This simple Python program is the md2pdf client application. It is intended to
be used with an `md2pdf-webserver` instance, running locally or remotely. 
See [the md2pdf-webserver hompage for more information](https://github.com/seanlano/md2pdf-webserver)


## Usage

Usage is quite simple, run `md2pdf-client -h` for more information:

```
usage: md2pdf_client.py [-h] (-f FILEPATH | --set-default OPTION VALUE)
                        [-s ADDRESS[:PORT]] [--proto {http,https}]
                        [-t TEMPLATE]

md2pdf client - connect to an md2pdf server and create a PDF file

optional arguments:
  -h, --help            show this help message and exit
  -f FILEPATH, --file FILEPATH
                        Input Markdown file to be converted
  --set-default OPTION VALUE
                        Change a default value for an option. Use the full
                        argument name, separated by a space, e.g.: '--set-
                        default proto https' or '--set-default server
                        192.168.1.1:9090'
  -s ADDRESS[:PORT], --server ADDRESS[:PORT]
                        Server address to request PDF generation from. Use
                        hostname or IP address, and port number if required
                        (i.e. '127.0.0.1:9090', or 'my-host.com:8888'). If
                        port is not specified, port 80 will be used
  --proto {http,https}  Protocol to use
  -t TEMPLATE, --template TEMPLATE
                        Template to use, instead of the server default
                        (include the file extension)
```

## Usage hints

- Don't forget to set a default port when you set the default server! You probably won't be using port 80, so make sure you set it correctly, with something like `md2pdf-client --set-default server 1.2.3.4:9090` or `md2pdf-client --set-default server hostname.tld:9090`. Don't include the protocol here. 
- `md2pdf-webserver` by default doesn't do HTTPS - but it would be possible to put it behind a HTTPS reverse proxy. If that is the case, don't forget to set the default protocol with `md2pdf-client --set-default proto https`
- If you use the `--template` option, don't forget that the template must also exist in the server - you can't use a local template (at least not yet).
- If something doesn't work on the server end, you should get a `.log` file in the same directory as your input Markdown file - take a look in there for more information. 
- If something doesn't work on the client end, it can be helpful to run `md2pdf-client` from the command line to check the output.

## Installation

### Snap Package 

`md2pdf-client` is available as an Ubuntu Snap package. You can install it with :

```
$ sudo snap install --candidate md2pdf-client
```
I haven't yet released it to the "stable" category - it needs some more testing before that happens. 

The packaging is done automatically by Launchpad, based on the Snapcraft config [in this repo](https://github.com/seanlano/md2pdf-client-snap). 

### Direct Python script

It can also be run as a Python script: 

```
python3 md2pdf_client.py -f <file>
```

## License

This project is released under the terms of the GNU Affero GPL version 3 (or
later). Please see [LICENSE](LICENSE) for details.

## Thanks

The base of my (very crappy) icon is from the standard [GNOME icons](https://commons.wikimedia.org/wiki/GNOME_Desktop_icons). These are GPL licensed. 
