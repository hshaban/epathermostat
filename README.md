This a fork of the EPA thermostat metric repository. It is a custom version developed for a study of thermostat performance in Northwestern USA sponsored by NEEA.

Connected Thermostat draft field savings metrics module
=======================================================

Calculate temperature/run-time savings for connected thermostats using this
package.

Usage
-----
You'll need to generate a metadata file that contains general information about the thermostats.
Then, you'll need the hourly thermostat telemetry files.

Both of these file types need to conform to the EPA V2 specification.

Start by creating a virtual environment for this analysis. Some older components of the EPA library rely on Python 3.7, so make
sure you create a Python 3.7 environment. 
```
# if using virtualenvwrapper (see https://virtualenvwrapper.readthedocs.org/en/latest/install.html)
$ mkvirtualenv -p python3.7 thermostat_nw
(thermostat_nw)$ conda install shapely #May be required on Windows if you get lib_geos errors (or install wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#shapely)
(thermostat_nw)$ pip install thermostat-nw
```
Then, create an analysis script as follows:
```
import os

from thermostat_nw.importers import from_csv
from thermostat_nw.exporters import metrics_to_csv
from thermostat_nw.multiple import multiple_thermostat_calculate_epa_field_savings_metrics

data_dir = '/home/thermostat_nw' # Change this to the folder that contains the metdata and thermostat telemetry files
metadata_filename = os.path.join(data_dir, "metadata.csv") # Change the file name to match your metadata file

thermostats = from_csv(metadata_filename, verbose=True)
metrics = multiple_thermostat_calculate_epa_field_savings_metrics(thermostats)
output_filename = os.path.join(data_dir, "thermostat_outputs.csv") 
metrics_df = metrics_to_csv(metrics, output_filename)

thermostats = from_csv(metadata_filename, verbose=True)
metrics_ed = multiple_thermostat_calculate_epa_field_savings_metrics(thermostats, how="entire_dataset")
output_filename_ed = os.path.join(data_dir, "thermostat_outputs_entire_dataset.csv") 
metrics_df_ed = metrics_to_csv(metrics_ed, output_filename_ed)

```
Finally, execute the script within your virtual environment.
```
(thermostat_nw)$ python script.py
```


Documentation
-------------

Technical documentation is on [Read the Docs](http://epathermostat.readthedocs.io/en/latest/).

For information about metrics and methods that were added beyond the EPA specification, please contact hassan@empowerdataworks.com.

