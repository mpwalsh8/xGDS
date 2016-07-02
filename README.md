
# xGDSImport.py
Python utility to import GDS files into Mentor Graphics XpeditionPCB.

This projects used the [Python GDSII library](https://pypi.python.org/pypi/python-gdsii) from Eugeniy Meshcheryakov.  The source code repository for this library no longer resolves so the source has been incorporated into this project.

## Usage
```
C:\Users\mike\Documents\xGDS>python xGDSImport.py --help
// 
// Xpedition GDS Import Utility
// 
// Version:  1.0-beta-2, Sat July 02 06:30:54 EDT 2016
// 

    -d --debug                Report detailed information while reading GDS
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


    
Usage: xGDSImport.py --gds <input.gds>
```

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
// Note:    End Time:  Sat, 02 Jul 2016 07:49:58
// Note:    Run Time:  0:00:06
// GDS import complete, check for errors. (xGDSImport.py)

C:\Users\mike\Documents\xGDS>
```

## Notes

This script is only supported on Windows.  There are no Python COM bindings available for Xpedition running on Linux.

## Compatibility

This script has been tested with Python 2.7 and Python 3.5.
