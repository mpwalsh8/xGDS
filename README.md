
# xGDSImport.py
Python utility to import GDS files into Mentor Graphics XpeditionPCB.

This projects used the [Python GDSII library](https://pypi.python.org/pypi/python-gdsii) from Eugeniy Meshcheryakov.  The source code repository for this library no longer resolves so the source has been incorporated into this project.

## Usage

    C:\Users\mike\Documents\xGDS>python xGDSImport.py --help
    // 
    // Xpedition GDS Import Utility
    // 
    // Version:  1.0-beta-2, Sat July 02 06:30:54 EDT 2016
    // 
    
    	-d --debugReport detailed information while reading GDS
    	-g --gui  Use GUI, default when missing --gds option
    	-i --gds <gdsfile>GDS input file
    	-h --help Display this help content
    	-l --lockserver   Lock Xpedition Server to improve performance
    	-p --progress Report progress during GDS import
    	-r --replace  Replace existing user layers when importing GDS
    	-s --shuffle  Shuffle color patterns assigned to GDS user layers
    	-t --transaction  Wrap GDS import in a Transaction to improve performance
    	-v --version  Print version number
    	-w --work <path>  Initial path for GDS file selection, default to current directory
    
    
    
    Usage: xGDSImport.py --gds <input.gds>


## Sample Execution


    C:\Users\mike\Documents\xGDS>python xGDSImport.py --gds P9_Flat.gds --replace --transaction
    // 
    // Xpedition GDS Import Utility
    // 
    // Version:  1.0-beta-2, Sat July 02 06:30:54 EDT 2016
    // 
    // 
    // Command line options
    // 
    // Note:  --gds set to:  P9_Flat.gds
    // Note:  --transaction option enabled
    // 
    // Note:  GDS Import Python script connected to PCB database "Demo-S.pcb".
    // Note:  GDS layer 74.30 will be imported.
    // Note:  GDS layer 5.3 will be imported.
    // Note:  GDS layer 5.4 will be imported.
    // Note:  Starting Transaction ...
    // Note:  User Layer "GDS_74.30" setup for GDS import.
    // Note:  User Layer "GDS_5.3" setup for GDS import.
    // Note:  User Layer "GDS_5.4" setup for GDS import.
    // Note:  Ending Transaction ...
    // Note:  Processed 426 records in GDS source file.
    // Note:  Start Time:  Sat, 02 Jul 2016 07:49:52
    // Note:End Time:  Sat, 02 Jul 2016 07:49:58
    // Note:Run Time:  0:00:06
    // GDS import complete, check for errors. (xGDSImport.py)
    
    C:\Users\mike\Documents\xGDS>


## Notes

- This script is only supported on Windows.  There are no Python COM bindings available for Xpedition running on Linux.
- To run the script, execute Python from the MGC PCB CMD window (a Windows Command Window with the environment initialized for the version of Xpedition being used).

## Limitations

1. Only flat GDS is supported.  Hierarchical GDS will import but the results will be incorrect.  The library cells will appear one time at the 0,0 point and be missing from the locations where they are instantiated.
2. The full GDS specification is not supported.  Boundary, Text, and Path elements are imported.  Node, Box, and not currently supported.
3. Path elements are rendered with round ends.  The line end encoding (PATHTYPE) is not currently supported.

## Compatibility

This script has been tested with the following:

- Python 2.7
- Python 3.5
- Xpedition VX.1.2 (XPI flow)

## Sample GDS Data

Sample GDS data is not easy to find as most is customer proprietary.  The Virginia Tech web site includes a number of tutorials based on an Up/Down Counter design.  The GDS file included with this script is a flattened version of the GDS file [available from the Va Tech web site](http://www.vtvt.ece.vt.edu/vlsidesign/updown_counter.gds "Up/Down Counter GDS File").
