#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set expandtab tabstop=4 shiftwidth=4:
#
#  xGDSImport.py - Import GDS into Xpedition
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
#    07/01/2016 - Cleaned up User Layer operations, assigned color patterns,
#                 added key bindings and other polish.
#
#    07/02/2016 - Added Python 2.7 and 3.5 compatibility.
#
#    07/06/2016 - Added option (command line only --erase) to remove all
#                 GDS user layers from database.  Added support for GDS Path
#                 and Text elements.
#

from __future__ import print_function
import os, sys, inspect, getopt, csv, time, datetime, random

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

##  Gracefully handle compatibility between Python 2.7 and 3.5
try:
    import Tkinter as TK, Tkconstants as TKConst, tkFileDialog as TKFileDialog
except ImportError:
    import tkinter as TK, tkinter.constants as TKConst, tkinter.filedialog as TKFileDialog

#  need access to Python's COM interface
#import pythoncom
import win32com.client
import win32com.client.gencache
from win32com.client import constants

DATE='Wed July 06 16:08:54 EDT 2016'
VERSION='1.0-beta-4'

# Check python version

if sys.version_info < ( 2, 6):
    # python too old, kill the script
    sys.exit("This script requires Python 2.6 or newer!")

##  Global variables to store the state variables which
##  control execution of the script.  We are using global
##  variables because it makes interaction with GUI easier.

debug = False
erase = True
gdsin = None
replace = False
progress = False
lockserver = False
shuffle = False
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
        
    except pythoncom.com_error(hr, msg, exc, arg):
        sys.exit("Terminating script, unable to obtain PCB Document.")

    key = docObj.Validate(0)
    licenseServer = win32com.client.gencache.EnsureDispatch("MGCPCBAutomationLicensing.Application")
    licenseToken = licenseServer.GetToken(key)

    try:
        docObj.Validate(licenseToken)
    except pythoncom.com_error(hr, msg, exc, arg):
        sys.exit("Terminating script, unable to obtain Automation license.")

    return docObj

##  General purpose print function to place
##  output on stderr
def tprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


##  Debug Output for GDS elements
def showData(rec):
    """Shows GDS data in a human-readable format."""
    if rec.tag_type == types.ASCII:
        return '"%s"' % rec.data.decode() # TODO escape
    elif rec.tag_type == types.BITARRAY:
        return str(rec.data)
    return ', '.join('{0}'.format(i) for i in rec.data)


##  Output messages to console and optionally to the Xpeditio/t
##  message window.  By default, all messages are sent to both.
def Transcript(msg, svrty = None, echo = True):
    global pcbApp

    if svrty == None:
        tprint("// {}".format(msg))
        if echo:
            pcbApp.Addins("Message Window").Control.AddTab("Output").AppendText("{}\n".format(msg))
    else:
        tprint("// {}:  {}".format(svrty.title(), msg))
        if echo:
            pcbApp.Addins("Message Window").Control.AddTab("Output").AppendText("{}:  {}\n".format(svrty.title(), msg))
    

##  BuildGUI
class BuildGUI(TK.Frame):
    handles = []
    widgets = {}

    def __init__(self, parent, gdsin=None, replace=True, progress=False, \
            lockserver=False, shuffle=False, transaction=False, work=os.getcwd()):
        TK.Frame.__init__(self, parent)

        ##  Init class properties
        self.parent = parent

        self.work = work
        self.replace = replace
        self.progress = progress
        self.lockserver = lockserver
        self.shuffle = shuffle
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

    def EscapeKey(self, event):
        self.Cancel()

    def Run(self):
        global erase, gdsin, replace, progress, lockserver, shuffle, transaction

        ##  Set the global variables based on the current state of the GUI

        gdsin = self.widgets['inputgds'].get()
        replace = self.widgets['opts.lf.rpl'].get()
        progress = self.widgets['opts.lf.rp'].get()
        lockserver = self.widgets['opts.lf.ls'].get()
        shuffle = self.widgets['opts.lf.sfl'].get()
        transaction = self.widgets['opts.lf.tr'].get()

        self.quit()

    def ReturnKey(self, event):
        self.Run()

    ##  Construct the GUI
    def InitGUI(self):

        gdsFileTypes = (
            ('GDS', '*.gds *.GDS'),
            ('GDS2', '*.gds2 *.GDS2'),
            ('GDSII', '*.gdsii *.GDSII'),
            ('All Files', '*') )

        self.parent.title('Import GDS Layers v' + VERSION)
        self.pack(fill=TKConst.BOTH, expand=True)

        ##  Dictionary for file input entry / browse button pairs
        fileinputs = {
            'inputgds' : ('Input GDS File', gdsFileTypes, 0, self.work),
        }

        ##  Create the outer frame
        self.widgets['ofr'] = TK.Frame(self, relief=TKConst.FLAT)
        self.widgets['ofr'].pack(fill=TKConst.BOTH, expand=True)

        ##  Create the inner frame
        self.widgets['ifr'] = TK.Frame(self.widgets['ofr'], padx=5, pady=5, borderwidth=5, relief=TKConst.FLAT)
        self.widgets['ifr'].pack(fill=TKConst.BOTH, expand=True)

        ##  Create file entry box / browse button pairs
        ##  Each pair sits insite a label frame
        row = 0
        for (key, value) in fileinputs.items():
            #tprint("Key:  " + key)
            #tprint("Row:  %s" % row)

            self.widgets[key] = TK.StringVar()
            self.widgets[key + '.lf'] = TK.LabelFrame(self.widgets['ifr'], \
                text=value[0], padx=5, pady=5)
            self.widgets[key + '.lf'].grid(row=value[2], column=0, pady=10)
 
            self.widgets[key + '.e'] = TK.Entry(self.widgets[key + '.lf'], width=60, \
                relief=TKConst.SUNKEN, textvariable=self.widgets[key], borderwidth=2)
            self.widgets[key + '.e'].pack(fill=TKConst.X, side=TKConst.LEFT, padx=5, expand=True)
            self.widgets[key + '.b'] = TK.Button(self.widgets[key + '.lf'], text=value[0] + ' ...', width=15, \
                command=(lambda key=key, value=value: self.widgets[key].set(TKFileDialog.askopenfilename(filetypes=value[1],
                initialdir=value[3]))))
            self.widgets[key + '.b'].pack(fill=TKConst.X, side=TKConst.RIGHT, padx=5, expand=False)

            row +=1

        ##  Handle existing values passed in from command line
        if self.gdsin is not None:
            self.widgets['inputgds'].set(self.gdsin)

        ##  Options to drive the mapping
        self.widgets['opts.lf'] = TK.LabelFrame(self.widgets['ifr'], text='Options', padx=5, pady=5)
        self.widgets['opts.lf'].grid(row=4, column=0, sticky=TKConst.E + TKConst.W, pady=10)

        self.widgets['opts.lf.rpl'] = TK.BooleanVar()
        self.widgets['opts.lf.rpl'].set(self.replace)
        self.widgets['opts.lf.rpl.cb'] = TK.Checkbutton(self.widgets['opts.lf'], \
            text='Replace GDS layer content (previously imported GDS date will be deleted)', onvalue=True, \
            offvalue=False, variable=self.widgets['opts.lf.rpl'])
        self.widgets['opts.lf.rpl.cb'].grid(row=0, column=0, sticky=TKConst.W, padx=5)

        self.widgets['opts.lf.rp'] = TK.BooleanVar()
        self.widgets['opts.lf.rp'].set(self.progress)
        self.widgets['opts.lf.rp.cb'] = TK.Checkbutton(self.widgets['opts.lf'], \
            text='Report Progress (detailed progress messages during GDS import)', onvalue=True, \
            offvalue=False, variable=self.widgets['opts.lf.rp'])
        self.widgets['opts.lf.rp.cb'].grid(row=1, column=0, sticky=TKConst.W, padx=5)

        self.widgets['opts.lf.ls'] = TK.BooleanVar()
        self.widgets['opts.lf.ls'].set(self.lockserver)
        self.widgets['opts.lf.ls.cb'] = TK.Checkbutton(self.widgets['opts.lf'], \
            text='Lock Server (Lock Server during GDS import - improves performance)', onvalue=True, \
            offvalue=False, variable=self.widgets['opts.lf.ls'])
        self.widgets['opts.lf.ls.cb'].grid(row=2, column=0, sticky=TKConst.W, padx=5)

        self.widgets['opts.lf.tr'] = TK.BooleanVar()
        self.widgets['opts.lf.tr'].set(self.transaction)
        self.widgets['opts.lf.tr.cb'] = TK.Checkbutton(self.widgets['opts.lf'], \
            text='Use Transactions (wrap GDS import in a single transaction - improves performance)', onvalue=True, \
            offvalue=False, variable=self.widgets['opts.lf.tr'])
        self.widgets['opts.lf.tr.cb'].grid(row=3, column=0, sticky=TKConst.W, padx=5)

        self.widgets['opts.lf.sfl'] = TK.BooleanVar()
        self.widgets['opts.lf.sfl'].set(self.shuffle)
        self.widgets['opts.lf.sfl.cb'] = TK.Checkbutton(self.widgets['opts.lf'], \
            text='Shuffle Color Patterns (shuffle color pattern assignment)', onvalue=True, \
            offvalue=False, variable=self.widgets['opts.lf.sfl'])
        self.widgets['opts.lf.sfl.cb'].grid(row=4, column=0, sticky=TKConst.W, padx=5)

        ## Separator
        self.widgets['separator'] = TK.Frame(self.widgets['ofr'], height=2, borderwidth=2, relief=TKConst.SUNKEN)
        self.widgets['separator'].pack(fill=TKConst.X, expand=True, padx=5, pady=5)

        ##  Create the button frame
        self.widgets['bfr'] = TK.Frame(self.widgets['ofr'], padx=5, pady=5, borderwidth=5, relief=TKConst.FLAT)
        self.widgets['bfr'].pack(side=TKConst.BOTTOM, expand=False)

        ##  Buttons
        self.widgets['bfr.run'] = TK.Button(self.widgets['bfr'], text='Run', width=15, command=self.Run)
        self.widgets['bfr.run'].pack(fill=TKConst.Y, expand=False, side=TKConst.LEFT, padx=5)
        self.widgets['bfr.cancel'] = TK.Button(self.widgets['bfr'], text='Cancel', width=15, command=self.Cancel)
        self.widgets['bfr.cancel'].pack(fill=TKConst.Y, expand=False, side=TKConst.LEFT, padx=5)


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
    global erase, gdsin, progress, lockserver, replace, shuffle, transaction, work

    Version()

    ##  Parse command line

    try:
        opts, args = getopt.getopt(argv, "deghi:lprstvw:", [ \
            "debug", "erase", "gui", "help", "gds=", "lockserver", \
            "progress", "replaced", "shuffle", "transaction", \
            "version", "work="])
    except getopt.GetoptError as err:
        tprint(err)
        usage(os.path.basename(sys.argv[0]))
        sys.exit(2)

    ##  Only show version?
    if len([i for i, j in opts if i in ['-v', '--version']]):
        sys.exit(0)

    ##  Initialize variables

    rc = 0
    erase = False
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
        if opt in ("-e", "--erase"):
            erase = True
        if opt in ("-g", "--gui"):
            gui = True
        if opt in ("-i", "--gds"):
            gdsin = arg
            Transcript("{} set to:  {}".format(opt, arg), "note", False)
        if opt in ("-l", "--lockserver"):
            lockserver = True
        if opt in ("-p", "--progress"):
            progress = True
        if opt in ("-r", "--replace"):
            replace = True
            Transcript("{} option enabled".format(opt), "note", False)
        if opt in ("-s", "--shuffle"):
            shuffle = True
            Transcript("{} option enabled".format(opt), "note", False)
        if opt in ("-t", "--transaction"):
            transaction = True
            Transcript("{} option enabled".format(opt), "note", False)
        if opt in ("-w", "--work"):
            work = arg
            Transcript("{} set to:  {}".format(opt, arg), "note", False)

    Transcript("", None, False)

    ##  If Gui not specified but GDS not provided, default to GUI
    if gdsin is None and not gui:
        gui = True

    #  Try and launch Xpedition, it should already be open
    try:
        pcbApp = win32com.client.gencache.EnsureDispatch("MGCPCB.ExpeditionPCBApplication")
        pcbGui = pcbApp.Gui
        pcbUtil = pcbApp.Utility
        pcbApp.Visible = 1

    except pythoncom.com_error(hr, msg, exc, argv):
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
    if gui or gdsin is None:
        root = TK.Tk()
        root.title("Import GDS")
        #root.geometry("600x600+300+300")
        app = BuildGUI(root, gdsin, replace, progress, lockserver, shuffle, transaction, work)
        ##  Setup key binds for Run and Cancel
        root.bind('<Return>', app.ReturnKey)
        root.bind('<Escape>', app.EscapeKey)
        root.protocol("WM_DELETE_WINDOW", app.Cancel)
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

    ##  "Pre-scan" the GDS to gather up the layers that will be imported.
    gdslayers = []

    for struc in lib:
        for elem in struc:
            if isinstance(elem, Boundary):
                gdslayer = "{}.{}".format(elem.layer, elem.data_type)
            if isinstance(elem, Path):
                gdslayer = "{}.{}".format(elem.layer, elem.path_type)
            elif isinstance(elem, Text):
                gdslayer = "{}.{}".format(elem.layer, elem.text_type)
            elif isinstance(elem, Node):
                gdslayer = "{}.{}".format(elem.layer, elem.node_type)
            elif isinstance(elem, Box):
                gdslayer = "{}.{}".format(elem.layer, elem.box_type)

            if gdslayer not in gdslayers:
                gdslayers.append(gdslayer)

    for gdslayer in gdslayers:
        Transcript("GDS layer {} will be imported.".format(gdslayer), "note")

    ##  Lock the Server?
    if lockserver:
        ls = pcbApp.LockServer
        if ls:
            Transcript("Locking Server ...", "note")

    ##  Start Transaction?
    if transaction:
        trs = pcbDoc.TransactionStart(0)
        if trs:
            Transcript("Starting Transaction ...", "note")

    ##  Erase all GDS layers?
    if erase:
        for l in range(0, 255):
            for d in range(0, 255):
                uln = "GDS_{}.{}".format(l, d)
                ul = pcbDoc.FindUserLayer(uln)
                if ul != None:
                    Transcript("User Layer {} will be erased.".format(uln), "warning")
                    ##  Select All on the user layer
                    ug = pcbDoc.GetUserLayerGfxs(constants.epcbSelectAll, uln, False)

                    ##  Delete everything selected
                    if ug != None:
                        ug.Delete()
                    else:
                        Transcript("User Layer {} is empty.".format(uln), "note")
                    
                    ##  Select All text on the user layer
                    ut = pcbDoc.GetUserLayerTexts(constants.epcbSelectAll, ul.Name, False)

                    ##  Delete everything selected
                    if ut != None:
                        ut.Delete()
                    else:
                        Transcript("User Layer {} has no text.".format(ul.Name), "note")
                
                    ##  Delete the user layer - it will be recreated on import
                    try:
                        ul.Delete()
                    except:
                        Transcript("User Layer {} was not removed.  Is it empty?".format(ul.Name), "warning")


    ##  Replace existing layers?
    if replace:
        for gdslayer in gdslayers:
            uln = "GDS_{}".format(gdslayer)
            ul = pcbDoc.FindUserLayer(uln)
            if ul != None:
                Transcript("User Layer {} will be replaced.".format(uln), "warning")
                ##  Select All on the user layer
                ug = pcbDoc.GetUserLayerGfxs(constants.epcbSelectAll, uln, False)

                ##  Delete everything selected
                if ug != None:
                    ug.Delete()
                else:
                    Transcript("User Layer {} is empty.".format(uln), "note")
                    
                ##  Select All text on the user layer
                ut = pcbDoc.GetUserLayerTexts(constants.epcbSelectAll, ul.Name, False)

                ##  Delete everything selected
                if ut != None:
                    ut.Delete()
                else:
                    Transcript("User Layer {} has no text.".format(ul.Name), "note")
                
                ##  Delete the user layer - it will be recreated on import
                try:
                    ul.Delete()
                except:
                    Transcript("User Layer {} was not removed.  Is it empty?".format(ul.Name), "warning")


    ##  Setup User Layers for GDS import
    colorpatterns = [ \
        pcbApp.Utility.NewColorPattern(255, 0, 0, 100, 14, False, False),       # Red  \
        pcbApp.Utility.NewColorPattern(0, 255, 0, 100, 14, False, False),       # Blue \
        pcbApp.Utility.NewColorPattern(0, 0, 255, 100, 14, False, False),       # Green \
        pcbApp.Utility.NewColorPattern(255, 0, 255, 100, 14, False, False),     # Purple \
        pcbApp.Utility.NewColorPattern(255, 255, 0, 100, 14, False, False),     # Yellow \
        pcbApp.Utility.NewColorPattern(0, 255, 255, 100, 14, False, False),     # Aqua \
    ]

    ##  Shuffle the color patterns just to mix up the colors ...
    if shuffle:
        random.shuffle(colorpatterns)

    ##  Loop through the layers in the GDS file and set up a user layer for each
    for gdslayer in gdslayers:
        uln = "GDS_{}".format(gdslayer)
        cp = colorpatterns[(gdslayers.index(gdslayer) % len(colorpatterns))]
        setupUserLayer(uln, cp)

    ##  Traverse the design, looking for layers to import
    for struc in lib:
        for elem in struc:
            if progress:
                Transcript("GDS Element on Layer {}" .format(elem.layer), "note")
                if isinstance(elem, Boundary):
                    Transcript("GDS Element of Datatype {}".format(elem.data_type), "note")
                if isinstance(elem, Path):
                    Transcript("GDS Element of Pathtype {}".format(elem.path_type), "note")
                elif isinstance(elem, Text):
                    Transcript("GDS Element of Texttype {}".format(elem.text_type), "note")
                elif isinstance(elem, Node):
                    Transcript("GDS Element of Nodetype {}".format(elem.node_type), "note")
                elif isinstance(elem, Box):
                    Transcript("GDS Element of Boxtype {}".format(elem.box_type), "note")


            if isinstance(elem, Boundary):
                if progress:
                    Transcript("GDS Boundary element found ...", "note")
                drawBoundry(elem)
            elif isinstance(elem, Path):
                if progress:
                    Transcript("GDS Path element found ...", "note")
                drawPath(elem)
            elif isinstance(elem, Text):
                if progress:
                    Transcript("GDS Text element found ...", "note")
                drawText(elem)
            elif isinstance(elem, Node):
                if progress:
                    Transcript("GDS Node element found ...", "note")
                Transcript("GDS Node element has not been implemented.", "warning")
            elif isinstance(elem, Box):
                if progress:
                    Transcript("GDS Box element found ...", "note")
                Transcript("GDS Box element has not been implemented.", "warning")

            rc+= 1
#            if rc == 25:
#                break
        
    ##  End Transaction?
    if transaction:
        tre = pcbDoc.TransactionEnd(True)
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
def setupUserLayer(uln, cp):
    global pcbApp, pcbDoc, pcbUtil

    ul = pcbDoc.FindUserLayer(uln)

    ##  If the user layer doesn't exist, it needs to be  created

    if ul == None:
        ul = pcbDoc.SetupParameter.PutUserLayer(uln)

    #  Make sure the layer was created and make it visible

    if ul == None:
        Transcript("Unabled to setup User Layer \"{}\" for GDS import.".format(uln), "error")
    else:
        ##  Get a reference to Display Control
        dc = pcbDoc.ActiveView.DisplayControl

        ##  Handle for Global Display Control object
        gbl = dc.Global

        ##  Handle for User Layer
        ul = pcbDoc.FindUserLayer(uln)

	    ## Make sure the User Layer is visible
        pcbDoc.ActiveView.DisplayControl.SetUserLayer(ul, True)

        ##  Change the pattern of the User Layer to the color pattern
        gbl.SetUserLayerColor(uln, cp)

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
        tprint("GDS Boundary XY:  {}".format(str(elem.xy)), "debug")

    ##  Need to convert the elem.xy vertices into a points array ...
    X = []
    Y = []
    R = []

    ##  Need to convert Nanometers in the GDS file to microns ...
    ##
    ##  @TODO - extract actual units from GDS file and handle them properly!
    ##

    for xy in elem.xy:
        X.append(xy[0] * 0.001)  ## Assumed to be converting from nanometers to microns
        Y.append(xy[1] * 0.001)  ## Assumed to be converting from nanometers to microns
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

    ##  If the user layer doesn't exist, something is wrong ...
    if ul == None:
        Transcript("Unable to find User Layer \"{}\", Boundary element skipped.".format(uln), "error")
    else:
        pcbDoc.PutUserLayerGfx(ul, 5.0, len(X), xyr, True, None, constants.epcbUnitUM)


##
##  drawText
##
##  Draw the text referenced on a user layer in Xpedition
##
##  @TODO:  Support for the font size, angle, etc. - all of
##          the PRESENTATION aspects of text element.
##
def drawText(elem):
    global progress

    if progress:
        tprint("GDS Text XY:  {}".format(str(elem.xy)), "debug")
        tprint("GDS Text PRESENTATION:  {}".format(str(elem.presentation)), "debug")
        tprint("GDS Text MAG:  {}".format(str(elem.mag)), "debug")
        tprint("GDS Text ANGLE:  {}".format(str(elem.angle)), "debug")
        tprint("GDS Text STRANS:  {}".format(str(elem.strans)), "debug")
        tprint("GDS Text WIDTH:  {}".format(str(elem.width)), "debug")
        tprint("GDS Text STRING:  {}".format(str(elem.string)), "debug")

    ##  Need to convert Nanometers in the GDS file to microns ...
    ##
    ##  @TODO - extract actual units from GDS file and handle them properly!
    ##

    for xy in elem.xy:
        X = xy[0] * 0.001  ## Assumed to be converting from nanometers to microns
        Y = xy[1] * 0.001  ## Assumed to be converting from nanometers to microns

    uln = "GDS_{}.{}".format(elem.layer, elem.text_type)
    if progress:
        Transcript("Drawing Text on {}".format(uln), "note")

    ##  Check if GDS user layer has already been setup
    ul = pcbDoc.FindUserLayer(uln)

    ##  If the user layer doesn't exist, something is wrong ...
    if ul == None:
        Transcript("Unable to find User Layer \"{}\", Text element skipped.".format(uln), "error")
    else:
        pcbDoc.PutUserLayerText(elem.string, X, Y, ul, 1.0, 0, 0, \
            "std-proportional", 0, constants.epcbJustifyHCenter, \
            constants.epcbJustifyVCenter, None, constants.epcbUnitUM, \
            constants.epcbAngleUnitDegrees)


##
##  drawPath
##
##  Draw the path referenced on a user layer in Xpedition
##
##  @TODO:  Support for line encodings, etc - all of the
##          attributes of a path element.
##
def drawPath(elem):
    global progress

    if progress:
        tprint("GDS Path XY:  {}".format(str(elem.xy)), "debug")
        tprint("GDS Path WIDTH:  {}".format(str(elem.width)), "debug")
        tprint("GDS Path PATHTYPE:  {}".format(str(elem.path_type)), "debug")

    ##  A Path element with rounded ends (PATHTYPE == 1) is handled as a simple
    ##  line with a width.  Square ended paths (PATHTYPE == 0 or PATHTYPE == 2)
    ##  need to be converted from coordinate pairs to a polygon with the proper
    ##  line end handling.
    ##
    ##  For now all lines are handled with rounded ends ...

    ##  Need to convert the elem.xy vertices into a points array ...
    X = []
    Y = []
    R = []

    ##  Need to convert Nanometers in the GDS file to microns ...
    ##
    ##  @TODO - extract actual units from GDS file and handle them properly!
    ##

    for xy in elem.xy:
        X.append(xy[0] * 0.001)  ## Assumed to be converting from nanometers to microns
        Y.append(xy[1] * 0.001)  ## Assumed to be converting from nanometers to microns
        R.append(0.0)


    ##  Convert the lists into a Tuple to pass to Xpedition as a Points Array
    xyr = (tuple(X), tuple(Y), tuple(R))

    ##  Get the path width
    W = elem.width * 0.001  ## Assumed to be converting from nanometers to microns

    uln = "GDS_{}.{}".format(elem.layer, elem.data_type)
    if progress:
        Transcript("Drawing Path on {}".format(uln), "note")

    ##  Check if GDS user layer has already been setup
    ul = pcbDoc.FindUserLayer(uln)

    ##  If the user layer doesn't exist, something is wrong ...
    if ul == None:
        Transcript("Unable to find User Layer \"{}\", Boundary element skipped.".format(uln), "error")
    else:
        pcbDoc.PutUserLayerGfx(ul, W, len(X), xyr, False, None, constants.epcbUnitUM)


def usage(prog):
    usage = """
    -d --debug                Report detailed information while reading GDS
    -e --erase                Erase any existing GDS user layers matching GDS_L.D pattern
    -g --gui                  Use GUI, default when missing --gds option
    -i --gds <gdsfile>        GDS input file
    -h --help                 Display this help content
    -l --lockserver           Lock Xpedition Server to improve performance
    -p --progress             Report progress during GDS import
    -r --replace              Replace existing user layers when importing GDS
    -s --shuffle              Shuffle color patterns assigned to GDS user layers
    -t --transaction          Wrap GDS import in a Transaction to improve performance
    -v --version              Print version number
    -w --work <path>          Initial path for GDS file selection, default to current directory


    """
    tprint(usage)
    tprint('Usage: %s --gds <input.gds>' % prog)

if __name__ == '__main__':
    if (len(sys.argv) > 0):
        main(sys.argv[1:])
        Transcript("GDS import complete, check for errors. ({})".format((os.path.basename(sys.argv[0]))))
    else:
        usage(os.path.basename(sys.argv[0]))
        sys.exit(1)
    sys.exit(0)
