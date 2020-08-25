from thermostat.importers import from_csv
from thermostat.importers import get_single_thermostat
from thermostat.util.testing import get_data_path
from thermostat.core import Thermostat, CoreDaySet
from tempfile import TemporaryDirectory

import pandas as pd
import numpy as np
from numpy import nan

import pytest

# will be modified, recreate every time by scoping to function
@pytest.fixture(scope='function')
def thermostat_template():
    thermostat_id = "FAKE"
    heat_type = None
    heat_stage = None
    cool_type = None
    cool_stage = None
    zipcode = "FAKE"
    station = "FAKE"
    temperature_in = pd.Series([], dtype="Float64")
    temperature_out = pd.Series([], dtype="Float64")
    cool_runtime = pd.Series([], dtype="Float64")
    heat_runtime = pd.Series([], dtype="Float64")
    auxiliary_heat_runtime = pd.Series([], dtype="Float64")
    emergency_heat_runtime = pd.Series([], dtype="Float64")

    thermostat = Thermostat(
        thermostat_id,
        heat_type,
        heat_stage,
        cool_type,
        cool_stage,
        zipcode,
        station,
        temperature_in,
        temperature_out,
        cool_runtime,
        heat_runtime,
        auxiliary_heat_runtime,
        emergency_heat_runtime
    )
    return thermostat

# Note:
# The following fixtures can be quite slow without a prebuilt weather cache
# they the from_csv command fetches weather data. (This happens with builds on
# travis.)
# To speed this up, spoof the weather source.

@pytest.fixture(scope="session", params=["../data/metadata_type_1_single_utc_offset_0.csv"])
def thermostat_type_1_utc(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_type_1_single_utc_offset_bad.csv"])
def thermostat_type_1_utc_bad(request):
    thermostats = from_csv(get_data_path(request.param))

@pytest.fixture(scope="session", params=["../data/metadata_type_1_single_bad_zip.csv"])
def thermostat_type_1_zip_bad(request):
    thermostats = from_csv(get_data_path(request.param))
    return list(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_multiple_same_key.csv"])
def thermostats_multiple_same_key(request):
    thermostats = from_csv(get_data_path(request.param))
    return thermostats

@pytest.fixture(scope="session", params=["../data/metadata_type_1_single_too_many_minutes.csv"])
def thermostat_type_1_too_many_minutes(request):
    thermostats = from_csv(get_data_path(request.param))
    return list(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_type_1_single_data_out_of_order.csv"])
def thermostat_type_1_data_out_of_order(request):
    thermostats = from_csv(get_data_path(request.param))
    return list(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_type_1_single.csv"])
def thermostat_type_1(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_type_1_single.csv"])
def thermostat_type_1_cache(request):
    with TemporaryDirectory() as tempdir:
        thermostats = from_csv(get_data_path(request.param), save_cache=True, cache_path=tempdir)
        return next(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_type_2_single.csv"])
def thermostat_type_2(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_type_3_single.csv"])
def thermostat_type_3(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_type_4_single.csv"])
def thermostat_type_4(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_type_5_single.csv"])
def thermostat_type_5(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_single_zero_days.csv"])
def thermostat_zero_days(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)

@pytest.fixture(scope="session", params=["../data/metadata_single_emg_aux_constant_on_outlier.csv"])
def thermostat_emg_aux_constant_on_outlier(request):
    thermostats = from_csv(get_data_path(request.param))
    return thermostats

@pytest.fixture(scope="session")
def core_heating_day_set_type_1_mid_to_mid(thermostat_type_1):
    return thermostat_type_1.get_core_heating_days(method="year_mid_to_mid")[0]

@pytest.fixture(scope="session")
def core_heating_day_set_type_1_entire(thermostat_type_1):
    return thermostat_type_1.get_core_heating_days(method="entire_dataset")[0]

@pytest.fixture(scope="session")
def core_heating_day_set_type_2(thermostat_type_2):
    return thermostat_type_2.get_core_heating_days(method="year_mid_to_mid")[0]

@pytest.fixture(scope="session")
def core_heating_day_set_type_3(thermostat_type_3):
    return thermostat_type_3.get_core_heating_days(method="year_mid_to_mid")[0]

@pytest.fixture(scope="session")
def core_heating_day_set_type_4(thermostat_type_4):
    return thermostat_type_4.get_core_heating_days(method="year_mid_to_mid")[0]

@pytest.fixture(scope="session")
def core_cooling_day_set_type_1_end_to_end(thermostat_type_1):
    return thermostat_type_1.get_core_cooling_days(method="year_end_to_end")[0]

@pytest.fixture(scope="session")
def core_cooling_day_set_type_1_entire(thermostat_type_1):
    return thermostat_type_1.get_core_cooling_days(method="entire_dataset")[0]

@pytest.fixture(scope="session")
def core_cooling_day_set_type_1_empty(thermostat_type_1):
    core_cooling_day_set = thermostat_type_1.get_core_cooling_days(method="entire_dataset")[0]
    core_day_set = CoreDaySet(
        "empty",
        pd.Series(np.tile(False, core_cooling_day_set.daily.shape),
                  index=core_cooling_day_set.daily.index),
        pd.Series(np.tile(False, core_cooling_day_set.hourly.shape),
                  index=core_cooling_day_set.hourly.index),
        core_cooling_day_set.start_date,
        core_cooling_day_set.end_date
    )
    return core_day_set

@pytest.fixture(scope="session")
def core_heating_day_set_type_1_empty(thermostat_type_1):
    core_heating_day_set = thermostat_type_1.get_core_heating_days(method="entire_dataset")[0]
    core_day_set = CoreDaySet(
        "empty",
        pd.Series(np.tile(False, core_heating_day_set.daily.shape),
                  index=core_heating_day_set.daily.index),
        pd.Series(np.tile(False, core_heating_day_set.hourly.shape),
                  index=core_heating_day_set.hourly.index),
        core_heating_day_set.start_date,
        core_heating_day_set.end_date
    )
    return core_day_set

@pytest.fixture(scope="session")
def core_cooling_day_set_type_2(thermostat_type_2):
    return thermostat_type_2.get_core_cooling_days(method="year_end_to_end")[0]

@pytest.fixture(scope="session")
def core_cooling_day_set_type_3(thermostat_type_3):
    return thermostat_type_3.get_core_cooling_days(method="year_end_to_end")[0]

@pytest.fixture(scope="session")
def core_cooling_day_set_type_5(thermostat_type_5):
    return thermostat_type_5.get_core_cooling_days(method="year_end_to_end")[0]

@pytest.fixture(scope="session")
def metrics_type_1_data():

    # this data comes from a script in scripts/test_data_generation.ipynb

    data = [{'sw_version': '2.0.0',
      'ct_identifier': '8465829e-df0d-449e-97bf-96317c24dec3',
      'heat_type': 'heat_pump_electric_backup',
      'heat_stage': 'single_stage',
      'cool_type': 'heat_pump',
      'cool_stage': '',
      'heating_or_cooling': 'cooling_ALL',
      'zipcode': '62223',
      'station': '725314',
      'climate_zone': 'Mixed-Humid',
      'start_date': '2011-01-01T00:00:00',
      'end_date': '2014-12-31T00:00:00',
      'n_days_in_inputfile_date_range': 1460,
      'n_days_both_heating_and_cooling': 212,
      'n_days_insufficient_data': 0,
      'n_core_cooling_days': 298,
      'baseline_percentile_core_cooling_comfort_temperature': 69.5,
      'regional_average_baseline_cooling_comfort_temperature': 73.0,
      'percent_savings_baseline_percentile': 43.87225605491626,
      'avoided_daily_mean_core_day_runtime_baseline_percentile': 192.6452711173845,
      'avoided_total_core_day_runtime_baseline_percentile': 57408.29079298058,
      'baseline_daily_mean_core_day_runtime_baseline_percentile': 439.1050026610086,
      'baseline_total_core_day_runtime_baseline_percentile': 130853.29079298057,
      '_daily_mean_core_day_demand_baseline_baseline_percentile': 9.965985121585168,
      'percent_savings_baseline_regional': 21.431882976273748,
      'avoided_daily_mean_core_day_runtime_baseline_regional': 67.22951147234052,
      'avoided_total_core_day_runtime_baseline_regional': 20034.394418757474,
      'baseline_daily_mean_core_day_runtime_baseline_regional': 313.6892430159647,
      'baseline_total_core_day_runtime_baseline_regional': 93479.39441875747,
      '_daily_mean_core_day_demand_baseline_baseline_regional': 7.119532480279844,
      'mean_demand': 5.593682610648467,
      'tau': -0.8140890893843148,
      'alpha': 44.060371082629665,
      'mean_sq_err': 376.91070575662627,
      'root_mean_sq_err': 19.414188259018875,
      'cv_root_mean_sq_err': 0.07877225272227686,
      'mean_abs_pct_err': 0.05022801373339975,
      'mean_abs_err': 12.379182780703172,
      'total_core_cooling_runtime': 73445.0,
      'daily_mean_core_cooling_runtime': 246.45973154362417,
      'core_cooling_days_mean_indoor_temperature': 73.95551360924682,
      'core_cooling_days_mean_outdoor_temperature': 79.8280110067114,
      'core_mean_indoor_temperature': 73.95551360924682,
      'core_mean_outdoor_temperature': 79.8280110067114},
     {'sw_version': '2.0.0',
      'ct_identifier': '8465829e-df0d-449e-97bf-96317c24dec3',
      'heat_type': 'heat_pump_electric_backup',
      'heat_stage': 'single_stage',
      'cool_type': 'heat_pump',
      'cool_stage': '',
      'heating_or_cooling': 'heating_ALL',
      'zipcode': '62223',
      'station': '725314',
      'climate_zone': 'Mixed-Humid',
      'start_date': '2011-01-01T00:00:00',
      'end_date': '2014-12-31T00:00:00',
      'n_days_in_inputfile_date_range': 1460,
      'n_days_both_heating_and_cooling': 212,
      'n_days_insufficient_data': 0,
      'n_core_heating_days': 900,
      'baseline_percentile_core_heating_comfort_temperature': 69.5,
      'regional_average_baseline_heating_comfort_temperature': 69,
      'percent_savings_baseline_percentile': 10.646212402565268,
      'avoided_daily_mean_core_day_runtime_baseline_percentile': 92.14266008640676,
      'avoided_total_core_day_runtime_baseline_percentile': 82928.39407776609,
      'baseline_daily_mean_core_day_runtime_baseline_percentile': 865.4971045308511,
      'baseline_total_core_day_runtime_baseline_percentile': 778947.394077766,
      '_daily_mean_core_day_demand_baseline_baseline_percentile': 27.2900014700134,
      'percent_savings_baseline_regional': 9.032887220026936,
      'avoided_daily_mean_core_day_runtime_baseline_regional': 76.79284594499276,
      'avoided_total_core_day_runtime_baseline_regional': 69113.56135049349,
      'baseline_daily_mean_core_day_runtime_baseline_regional': 850.1472903894372,
      'baseline_total_core_day_runtime_baseline_regional': 765132.5613504935,
      '_daily_mean_core_day_demand_baseline_baseline_regional': 26.80600626276116,
      'mean_demand': 24.384649948852587,
      'tau': -2.339467303651741,
      'alpha': 31.714806079503898,
      'mean_sq_err': 6867.464909335243,
      'root_mean_sq_err': 82.87016899545483,
      'cv_root_mean_sq_err': 0.10715677603040916,
      'mean_abs_pct_err': 0.0716637864248528,
      'mean_abs_err': 55.421507737377354,
      'total_core_heating_runtime': 696019.0,
      'daily_mean_core_heating_runtime': 773.3544444444444,
      'core_heating_days_mean_indoor_temperature': 66.69662453118488,
      'core_heating_days_mean_outdoor_temperature': 44.673292695833325,
      'core_mean_indoor_temperature': 66.69662453118488,
      'core_mean_outdoor_temperature': 44.673292695833325,
      'total_auxiliary_heating_core_day_runtime': 145730.0,
      'total_emergency_heating_core_day_runtime': 2164.0,
      'rhu1_00F_to_05F': nan,
      'rhu1_05F_to_10F': 0.35810185185185184,
      'rhu1_10F_to_15F': 0.36336805555555557,
      'rhu1_15F_to_20F': 0.37900691389063484,
      'rhu1_20F_to_25F': 0.375673443706005,
      'rhu1_25F_to_30F': 0.3318400322150354,
      'rhu1_30F_to_35F': 0.28432496802364043,
      'rhu1_35F_to_40F': 0.19741898266605878,
      'rhu1_40F_to_45F': 0.15271363589013506,
      'rhu1_45F_to_50F': 0.09249776186213071,
      'rhu1_50F_to_55F': 0.052322643343051506,
      'rhu1_55F_to_60F': 0.028319891645631964,
      'rhu1_30F_to_45F': 0.22154695797667256,
      'rhu2_00F_to_05F': nan,
      'rhu2_05F_to_10F': 0.35810185185185184,
      'rhu2_10F_to_15F': 0.36336805555555557,
      'rhu2_15F_to_20F': 0.37900691389063484,
      'rhu2_20F_to_25F': 0.375673443706005,
      'rhu2_25F_to_30F': 0.3318400322150354,
      'rhu2_30F_to_35F': 0.28432496802364043,
      'rhu2_35F_to_40F': 0.19741898266605878,
      'rhu2_40F_to_45F': 0.15271363589013506,
      'rhu2_45F_to_50F': 0.09249776186213071,
      'rhu2_50F_to_55F': 0.052322643343051506,
      'rhu2_55F_to_60F': 0.028319891645631964,
      'rhu2_30F_to_45F': 0.22154695797667256}]
    return data
