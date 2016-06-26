#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set expandtab tabstop=4 shiftwidth=4:
#
#  xGDS.py - import GDS into Xpedition
#
#  (c) June 2016 - Mentor Graphics Corporation
#   
#  Mike Walsh - mike_walsh@mentor.com
#
#  Mentor Graphics Corporation
#  1001 Winstead Drive, Suite 380
#  Cary, North Carolina 27513
#
#  This software is NOT officially supported by Mentor Graphics.
#
#  ####################################################################
#  ####################################################################
#  ## The following  software  is  "freeware" which  Mentor Graphics ##
#  ## Corporation  provides as a courtesy  to our users.  "freeware" ##
#  ## is provided  "as is" and  Mentor  Graphics makes no warranties ##
#  ## with  respect  to "freeware",  either  expressed  or  implied, ##
#  ## including any implied warranties of merchantability or fitness ##
#  ## for a particular purpose.                                      ##
#  ####################################################################
#  ####################################################################
#
#  Change Log:
#
#    06/26/2016 - Initial implementation.  This script leverages examples
#                 in the python-gdsii module library.  More details on
#                 the library:  https://pypi.python.org/pypi/python-gdsii
#

from __future__ import print_function

import os, sys, inspect, getopt, csv, time, datetime

##  Set the Python path so the GDSII library can be imported from directory
##  where this script was run from.  The Python function realpath() will make
##  your script run, even if you symlink it :)
#cmd_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe()))[0]))
#if cmd_folder not in sys.path:
#    sys.path.insert(0, cmd_folder)

# use this if you want to include modules from a subfolder
cmd_subfolder = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile(inspect.currentframe()))[0],"python-gdsii-0.2.1")))
if cmd_subfolder not in sys.path:
    sys.path.insert(0, cmd_subfolder)


from gdsii import types
from gdsii.record import Record
from gdsii.library import Library
from gdsii.elements import *

import Tkinter, Tkconstants, tkFileDialog

#  need access to Python's COM interface
import win32com.client
import pythoncom

DATE='Sat June 25 15:55:54 EDT 2016'
VERSION='1.0-beta-1'

# Check python version

if sys.version_info < ( 2, 6):
    # python too old, kill the script
    sys.exit("This script requires Python 2.6 or newer!")

##  Global variables to store the layer mapping data
##  We are using global variables because the mapping
##  can be read from a CSV file and then modified via
##  the GUI.

debug = False
gdsin = None
progress = False
lockserver = False
transaction = False
work = None

##  Global variables to store the Xpedition application
##  and document objects so they don't need to be passed.

pcbApp = None
pcbDoc = None
pcbGui = None
pcbUtil = None

#  licensing function
#
#  returns docObj if successful, None otherwise
#
def GetLicensedDoc(appObj):
    try:
        docObj = appObj.ActiveDocument
        #print docObj
        
    except pythoncom.com_error, (hr, msg, exc, arg):
        sys.exit("Terminating script, unable to obtain PCB Document.")

    key = docObj.Validate(0)
    licenseServer = win32com.client.Dispatch("MGCPCBAutomationLicensing.Application")
    licenseToken = licenseServer.GetToken(key)

    try:
        docObj.Validate(licenseToken)
    except pythoncom.com_error, (hr, msg, exc, arg):
        sys.exit("Terminating script, unable to obtain Automation license.")

    return docObj

##  General purpose print function to place
##  output on stderr
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


##  Debug Output for GDS elements
def showData(rec):
    """Shows data in a human-readable format."""
    if rec.tag_type == types.ASCII:
        return '"%s"' % rec.data.decode() # TODO escape
    elif rec.tag_type == types.BITARRAY:
        return str(rec.data)
    return ', '.join('{0}'.format(i) for i in rec.data)


##  Output messages to console and optionally to the Xpedition
##  message window.  By default, all messages are sent to both.
def Transcript(msg, svrty = None, echo = True):
    global pcbApp

    if svrty == None:
        eprint("// {}".format(msg))
        if echo:
            pcbApp.Addins("Message Window").Control.AddTab("Output").AppendText("{}\n".format(msg))
    else:
        eprint("// {}:  {}".format(svrty.title(), msg))
        if echo:
            pcbApp.Addins("Message Window").Control.AddTab("Output").AppendText("{}:  {}\n".format(svrty.title(), msg))
    

##  BuildGUI
class BuildGUI(Tkinter.Frame):
    handles = []
    widgets = {}

    def __init__(self, parent, gdsin=None, progress=False, lockserver=False, transaction=False, work=os.getcwd()):
        Tkinter.Frame.__init__(self, parent)

        ##  Init class properties
        self.parent = parent

        self.work = work
        self.progress = progress
        self.lockserver = lockserver
        self.transaction = transaction
        self.gdsin = gdsin

        ##  Construct the GUI
        self.InitGUI()

    ##  Callback for input GDS file change 
    def InputGDSFileCallBack(self, igds, ogds):
        Transcript("Input GDS File Change:  P{}".format(igds.get()), "note")
        self.gdsin = igds.get()

    def Cancel(self):
        self.quit()
        Transcript("GDS import canceled, no action performed.", "warning")
        sys.exit(2)

    def Run(self):
        global gdsin, progress, lockserver, transaction

        ##  Set the global variables based on the current state of the GUI

        gdsin = self.widgets['inputgds'].get()
        progress = self.widgets['opts.lf.rp'].get()
        lockserver = self.widgets['opts.lf.ls'].get()
        transaction = self.widgets['opts.lf.tr'].get()

        self.quit()

    ##  Construct the GUI
    def InitGUI(self):

        gdsFileTypes = (
            ('GDS', '*.gds *.GDS'),
            ('GDS2', '*.gds2 *.GDS2'),
            ('GDSII', '*.gdsii *.GDSII'),
            ('All Files', '*') )

        self.parent.title('Import GDS Layers v' + VERSION)
        self.pack(fill=Tkconstants.BOTH, expand=True)

        ##  Dictionary for file input entry / browse button pairs
        fileinputs = {
            'inputgds' : ('Input GDS File', gdsFileTypes, 0, self.work),
        }

        ##  Create the outer frame
        self.widgets['ofr'] = Tkinter.Frame(self, relief=Tkconstants.FLAT)
        self.widgets['ofr'].pack(fill=Tkconstants.BOTH, expand=True)

        ##  Create the inner frame
        self.widgets['ifr'] = Tkinter.Frame(self.widgets['ofr'], padx=5, pady=5, borderwidth=5, relief=Tkconstants.FLAT)
        self.widgets['ifr'].pack(fill=Tkconstants.BOTH, expand=True)

        ##  Create file entry box / browse button pairs
        ##  Each pair sits insite a label frame
        row = 0
        for (key, value) in fileinputs.items():
            #eprint("Key:  " + key)
            #eprint("Row:  %s" % row)

            self.widgets[key] = Tkinter.StringVar()
            self.widgets[key + '.lf'] = Tkinter.LabelFrame(self.widgets['ifr'], \
                text=value[0], padx=5, pady=5)
            self.widgets[key + '.lf'].grid(row=value[2], column=0, pady=10)
 
            self.widgets[key + '.e'] = Tkinter.Entry(self.widgets[key + '.lf'], width=60, \
                relief=Tkconstants.SUNKEN, textvariable=self.widgets[key], borderwidth=2)
            self.widgets[key + '.e'].pack(fill=Tkconstants.X, side=Tkconstants.LEFT, padx=5, expand=True)
            self.widgets[key + '.b'] = Tkinter.Button(self.widgets[key + '.lf'], text=value[0] + ' ...', width=15, \
                command=(lambda key=key, value=value: self.widgets[key].set(tkFileDialog.askopenfilename(filetypes=value[1],
                initialdir=value[3]))))
            self.widgets[key + '.b'].pack(fill=Tkconstants.X, side=Tkconstants.RIGHT, padx=5, expand=False)

            row +=1

        ##  Handle existing values passed in from command line
        if self.gdsin is not None:
            self.widgets['inputgds'].set(self.gdsin)

        ##  Options to drive the mapping
        self.widgets['opts.lf'] = Tkinter.LabelFrame(self.widgets['ifr'], text='Options', padx=5, pady=5)
        self.widgets['opts.lf'].grid(row=4, column=0, sticky=Tkconstants.E + Tkconstants.W, pady=10)

        self.widgets['opts.lf.rp'] = Tkinter.BooleanVar()
        self.widgets['opts.lf.rp'].set(self.progress)
        self.widgets['opts.lf.rp.cb'] = Tkinter.Checkbutton(self.widgets['opts.lf'], \
            text='Report Progress (detailed progress messages during GDS import)', onvalue=True, \
            offvalue=False, variable=self.widgets['opts.lf.rp'])
        self.widgets['opts.lf.rp.cb'].grid(row=0, column=0, sticky=Tkconstants.W, padx=5)

        self.widgets['opts.lf.ls'] = Tkinter.BooleanVar()
        self.widgets['opts.lf.ls'].set(self.lockserver)
        self.widgets['opts.lf.ls.cb'] = Tkinter.Checkbutton(self.widgets['opts.lf'], \
            text='Lock Server (Lock Server during GDS import - improves performance)', onvalue=True, \
            offvalue=False, variable=self.widgets['opts.lf.ls'])
        self.widgets['opts.lf.ls.cb'].grid(row=1, column=0, sticky=Tkconstants.W, padx=5)

        self.widgets['opts.lf.tr'] = Tkinter.BooleanVar()
        self.widgets['opts.lf.tr'].set(self.transaction)
        self.widgets['opts.lf.tr.cb'] = Tkinter.Checkbutton(self.widgets['opts.lf'], \
            text='Use Transactions (wrap GDS import in a single transaction - improves performance)', onvalue=True, \
            offvalue=False, variable=self.widgets['opts.lf.tr'])
        self.widgets['opts.lf.tr.cb'].grid(row=2, column=0, sticky=Tkconstants.W, padx=5)

        ## Separator
        self.widgets['separator'] = Tkinter.Frame(self.widgets['ofr'], height=2, borderwidth=2, relief=Tkconstants.SUNKEN)
        self.widgets['separator'].pack(fill=Tkconstants.X, expand=True, padx=5, pady=5)

        ##  Create the button frame
        self.widgets['bfr'] = Tkinter.Frame(self.widgets['ofr'], padx=5, pady=5, borderwidth=5, relief=Tkconstants.FLAT)
        self.widgets['bfr'].pack(side=Tkconstants.BOTTOM, expand=False)

        ##  Buttons
        self.widgets['bfr.run'] = Tkinter.Button(self.widgets['bfr'], text='Run', width=15, command=self.Run)
        self.widgets['bfr.run'].pack(fill=Tkconstants.Y, expand=False, side=Tkconstants.LEFT, padx=5)
        self.widgets['bfr.cancel'] = Tkinter.Button(self.widgets['bfr'], text='Cancel', width=15, command=self.Cancel)
        self.widgets['bfr.cancel'].pack(fill=Tkconstants.Y, expand=False, side=Tkconstants.LEFT, padx=5)

        ##  Set up a call back on Input GDS File entry box so  we can set the output file name in auto mode
#        self.widgets['inputgds'].trace('w', lambda name, index, mode, \
#            igds=self.widgets['inputgds'], ogds=self.widgets['outputgds']: self.InputGDSFileCallBack(igds, ogds))

##  Version
def Version():
    Transcript("", None, False)
    Transcript("Xpedition GDS Import Utility", None, False)
    Transcript("", None, False)
    Transcript("Version:  {}, {}".format(VERSION, DATE), None, False)
    Transcript("", None, False)

##  Main routine
def main(argv):
    global pcbApp, pcbDoc, pcbGui, pcbUtil
    global gdsin, progress, lockserver, transaction, work

    Version()

    ##  Parse command line

    try:
        opts, args = getopt.getopt(argv, "dghi:lptvw:", \
            ["debug", "gui", "help", "gds=", "lockserver", "progress", "transaction", "version", "work="])
    except getopt.GetoptError, err:
        eprint(err)
        usage(os.path.basename(sys.argv[0]))
        sys.exit(2)

    ##  Only show version?
    if len([i for i, j in opts if i in ['-v', '--version']]):
        sys.exit(0)

    ##  Initialize variables

    rc = 0
    debug = False
    gui = False
    gdsin = None
    progress = False
    lockserver = False
    transaction = False

    work = os.getcwd()

    ##  Parse command line options

    Transcript("", None, False)
    Transcript("Command line options", None, False)
    Transcript("", None, False)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage(os.path.basename(sys.argv[0]))
            sys.exit(0)
        if opt in ("-d", "--debug"):
            debug = True
        if opt in ("-g", "--gui"):
            gui = True
        if opt in ("-i", "--gds"):
            gdsin = arg
            Transcript("{} set to:  {}".format(opt, arg), "note", False)
        if opt in ("-l", "--lockserver"):
            lockserver = True
        if opt in ("-p", "--progress"):
            progress = True
        if opt in ("-t", "--transaction"):
            transaction = True
            Transcript("{} enabled".format(opt), "note", False)
        if opt in ("-w", "--work"):
            work = arg
            Transcript("{} set to:  {}".format(opt, arg), "note", False)

    Transcript("", None, False)

    ##  Check for required options

    for r in ('gdsin', 'gdsin'):
        if globals()[r] is None and not gui:
            Transcript("--{} argument is required".format(r), "error", False)
            usage(os.path.basename(sys.argv[0]))
            sys.exit(2)

    #  Try and launch Xpedition, it should already be open
    try:
        pcbApp = win32com.client.Dispatch("MGCPCB.ExpeditionPCBApplication")
        pcbGui = pcbApp.Gui
        pcbUtil = pcbApp.Utility
        pcbApp.Visible = 1

    except pythoncom.com_error, (hr, msg, exc, argv):
        Transcript("Unabled to launch Xpedition", "error", False)
        sys.exit("Terminating script.")
        
    pcbApp.Gui.StatusBarText("Running Python GDS Import Script ...")

    #  Get a PCB document and make sure it is licensed
    #  If there isn't a design open, prompt the user for one

    while True:
        if pcbApp.ActiveDocument == None:
            pcbApp.Gui.ProcessCommand("File->Open")
        else:
            break
        
    pcbDoc = GetLicensedDoc(pcbApp)

    if pcbDoc == None:
        Transcript("No PCB database open, GDS import aborted.", "error")
    else:
        Transcript("GDS Import Python script connected to PCB database \"{}\".".format(pcbDoc.Name), "note")
        
    ##  Present GUI?
    if gui:
        root = Tkinter.Tk()
        root.title("Import GDS")
        #root.geometry("600x600+300+300")
        app = BuildGUI(root, gdsin, progress, lockserver, transaction, work)
        root.mainloop()

    ##  Make sure input file exists!
    if not os.path.isfile(gdsin):
        Transcript("--gds file ({}) does not exist".format(gdsin), "error")
        sys.exit(2)

    ##  Raw dump of the GDS file when in debug mode ...
    if debug:
        with open(gdsin, 'rb') as a_file:
            for rec in Record.iterate(a_file):
                if rec.tag_type == types.NODATA:
                    Transcript(rec.tag_name, "debug", False)
                else:
                    Transcript('{}: {}'.format(rec.tag_name, showData(rec)), "debug", False)

    ##  Capture the start time
    st = time.time()

    ##  Load the source GDS file
    with open(gdsin, 'rb') as stream:
        lib = Library.load(stream)

    ##  Lock the Server?
    if lockserver:
        ls = pcbApp.LockServer
        eprint(str(ls))
        if pcbApp.LockServer:
            Transcript("Locking Server ...", "note")

    ##  Start Transaction?
    if transaction:
        trs = pcbDoc.TransactionStart(0)
        eprint(str(trs))
        if trs:
            Transcript("Starting Transaction ...", "note")

    ##  Traverse the design, looking for layers to import

    for struc in lib:
        for elem in struc:
            ##  As objects are found in the GDS stream the layer
            ##  is adjusted per the mapping file.

            if progress:
                Transcript("GDS Element on Layer {}" .format(elem.layer), "note")
                Transcript("GDS Element of Datatype {}".format(elem.data_type), "note")

            if isinstance(elem, Boundary):
                if progress:
                    Transcript("GDS Boundary element found ...", "note")
                drawBoundry(elem)
            elif isinstance(elem, Path):
                if progress:
                    Transcript("GDS Path element found ...", "note")
                Transcript("GDS Path element has not been implemented.", "warning")
            elif isinstance(elem, Text):
                if progress:
                    Transcript("GDS Text element found ...", "note")
                Transcript("GDS Text element has not been implemented.", "warning")
            elif isinstance(elem, Node):
                if progress:
                    Transcript("GDS Node element found ...", "note")
                Transcript("GDS Node element has not been implemented.", "warning")
            elif isinstance(elem, Box):
                if progress:
                    Transcript("GDS Box element found ...", "note")
                Transcript("GDS Box element has not been implemented.", "warning")

            rc+= 1
        
    ##  Start Transaction?
    if transaction:
        tre = pcbDoc.TransactionEnd(True)
        eprint(str(tre))
        if tre:
            Transcript("Ending Transaction ...", "note")

    ##  Unlock the Server?
    if lockserver:
        pcbApp.UnlockServer
        Transcript("Unlocking Server ...", "note")

    ##  Capture the end time
    et = time.time()

    ##  Compute run time
    rt = datetime.timedelta(seconds=int(et-st))

    Transcript("Processed {} records in GDS source file.".format(rc), "note")
    Transcript("Start Time:  {}".format(time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(st))), "note")
    Transcript("  End Time:  {}".format(time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(et))), "note")
    Transcript("  Run Time:  {}".format(rt.__str__()), "note")

##
##  setupUserLayer
##
def setupUserLayer(uln):
    ul = pcbDoc.FindUserLayer(uln)

    ##  If the user layer doesn't exist, it needs to be  created

    if ul == None:
        ul = pcbDoc.SetupParameter.PutUserLayer(uln)

    #  Make sure the layer was created and make it visible

    if ul == None:
        Transcript("Unabled to setup User Layer \"{}\" for GDS import.".format(uln), "error")
    else:
        #ul = pcbDoc.ActiveView.DisplayControl.UserLayer(uln)
        #ul = True
        Transcript("User Layer \"{}\" setup for GDS import.".format(uln), "note")

    return ul

##
##  drawBoundry
##
##  Draw the polygon referenced on a user layer in Xpedition
##
def drawBoundry(elem):
    global progress

    if debug:
        eprint("GDS Boundary XY:  {}".format(str(elem.xy)), "debug")

    ##  Need to convert the elem.xy vertices into a points array ...
    X = []
    Y = []
    R = []

    ##  Need to convert Nanometers in the GDS file to microns ...
    for xy in elem.xy:
        X.append(xy[0] * 0.001)
        Y.append(xy[1] * 0.001)
        R.append(0.0)

    ##  Need to close the polygon by replicating the first element as the last.
    X.append(X[0])
    Y.append(Y[0])
    R.append(R[0])

    ##  Convert the lists into a Tuple to pass to Xpedition as a Points Array
    xyr = (tuple(X), tuple(Y), tuple(R))

    uln = "GDS_{}.{}".format(elem.layer, elem.data_type)
    if progress:
        Transcript("Drawing Boundary on {}".format(uln), "note")

    ##  Check if GDS user layer has already been setup
    ul = pcbDoc.FindUserLayer(uln)

    ##  If the user layer doesn't exist, it needs to be  created
    if ul == None:
        ul = setupUserLayer(uln)

    if ul == None:
        Transcript("Unable to find User Layer \"{}\", Boundary element skipped.".format(uln), "error")
    else:
        pcbDoc.PutUserLayerGfx(ul, 5.0, len(X), xyr, True, None, 5)
    #sys.exit(2)


def usage(prog):
    usage = """
    -g --gui                  Use GUI, default when missing --gds option
    -i --gds <gdsfile>        GDS input file
    -h --help                 Display this help content
    -l --lockserver           Lock Xpedition Server to improve performance
    -p --progress             Report progress during GDS import
    -t --transaction          Wrap GDS import in a Transaction to improve performance
    -v --version              Print version number
    -w --work <path>          Initial path for GDS file selection, default to current directory


    """
    eprint(usage)
    eprint('Usage: %s --gdsin <input.gds>' % prog)

if __name__ == '__main__':
    if (len(sys.argv) > 0):
        main(sys.argv[1:])
        Transcript("GDS import complete, check for errors. ({})".format((os.path.basename(sys.argv[0]))))
    else:
        usage(os.path.basename(sys.argv[0]))
        sys.exit(1)
    sys.exit(0)
