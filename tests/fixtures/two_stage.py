from thermostat_nw.importers import from_csv
from thermostat_nw.importers import get_single_thermostat
from thermostat_nw.util.testing import get_data_path
from thermostat_nw.core import Thermostat, CoreDaySet
from tempfile import TemporaryDirectory

import pandas as pd
import numpy as np
from numpy import nan

import pytest

""" Abbreviations used in this file:

    XX - Heating system type: fu (furnace), hp (heat pump),  er (electric resistance), ot (other)
    XX - Cooling system type: ce (central), hp (heat pump), 

    YY - backup: eb (electric backup), ne (non electric backup, df (dual fuel), na (N/A)

    Z - speed: 1 (single stage), 2 (two stage), v (variable)
"""


@pytest.fixture(
    scope="session",
    params=[
        "../data/two_stage/metadata_furnace_or_boiler_two_stage_central_two_stage.csv"
    ],
)
def thermostat_fu_2_ce_2(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)


@pytest.fixture(
    scope="session",
    params=[
        "../data/two_stage/metadata_furnace_or_boiler_two_stage_none_single_stage.csv"
    ],
)
def thermostat_furnace_or_boiler_two_stage_none_single_stage(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)


@pytest.fixture(
    scope="session",
    params=[
        "../data/two_stage/metadata_heat_pump_electric_backup_two_stage_heat_pump_two_stage.csv"
    ],
)
def thermostat_hpeb_2_hp_2(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)


@pytest.fixture(
    scope="session",
    params=["../data/two_stage/metadata_none_two_stage_heat_pump_two_stage.csv"],
)
def thermostat_na_2_hp_2(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)


@pytest.fixture(scope="session")
def core_heating_day_set_hpeb_2_hp_2_entire(thermostat_hpeb_2_hp_2):
    return thermostat_hpeb_2_hp_2.get_core_heating_days(method="entire_dataset")[0]


@pytest.fixture(scope="session")
def core_cooling_day_set_hpeb_2_hp_2_entire(thermostat_hpeb_2_hp_2):
    return thermostat_hpeb_2_hp_2.get_core_cooling_days(method="entire_dataset")[0]


@pytest.fixture(scope="session")
def metrics_hpeb_2_hp_2_data():

    data = [
        {
            "sw_version": "0.1.3",
            "ct_identifier": "c61badb0e0c0a7e06932de804af43111",
            "heat_type": "heat_pump_electric_backup",
            "heat_stage": "two_stage",
            "cool_type": "heat_pump",
            "cool_stage": "two_stage",
            "heating_or_cooling": "cooling_ALL",
            "zipcode": "27313",
            "station": "723170",
            "climate_zone": "Mixed-Humid",
            "start_date": "2018-01-01T00:00:00",
            "end_date": "2018-12-31T00:00:00",
            "n_days_in_inputfile_date_range": 364,
            "n_days_both_heating_and_cooling": 17,
            "n_days_insufficient_data": 51,
            "n_core_cooling_days": 160,
            "baseline_percentile_core_cooling_comfort_temperature": 70.8,
            "regional_average_baseline_cooling_comfort_temperature": 73.0,
            "percent_savings_baseline_percentile": 8.463929746930798,
            "avoided_daily_mean_core_day_runtime_baseline_percentile": 30.116193457075433,
            "avoided_total_core_day_runtime_baseline_percentile": 4818.590953132069,
            "baseline_daily_mean_core_day_runtime_baseline_percentile": 355.8180934570754,
            "baseline_total_core_day_runtime_baseline_percentile": 56930.89495313206,
            "_daily_mean_core_day_demand_baseline_baseline_percentile": 12.482150396333545,
            "percent_savings_baseline_regional": -9.403740362536968,
            "avoided_daily_mean_core_day_runtime_baseline_regional": -27.995533727051416,
            "avoided_total_core_day_runtime_baseline_regional": -4479.285396328227,
            "baseline_daily_mean_core_day_runtime_baseline_regional": 297.7063662729486,
            "baseline_total_core_day_runtime_baseline_regional": 47633.01860367178,
            "_daily_mean_core_day_demand_baseline_baseline_regional": 10.443582566756659,
            "percent_savings_baseline_hourly_regional": 1.5955805925503548,
            "avoided_daily_mean_core_day_runtime_baseline_hourly_regional": 5.281100520953169,
            "avoided_total_core_day_runtime_baseline_hourly_regional": 844.976083352507,
            "baseline_daily_mean_core_day_runtime_baseline_hourly_regional": 330.98300052095317,
            "baseline_total_core_day_runtime_baseline_hourly_regional": 52957.2800833525,
            "_daily_mean_core_day_demand_baseline_baseline_hourly_regional": 11.61093172916648,
            "mean_demand": 11.42566995588163,
            "tau": 8.651092771281144,
            "alpha": 28.506153359728142,
            "mean_sq_err": 2864.6067628539104,
            "root_mean_sq_err": 53.52202128894153,
            "cv_root_mean_sq_err": 0.16432824398304563,
            "mean_abs_pct_err": 0.1240485579833733,
            "mean_abs_err": 40.40285102744487,
            "cov_x": [[8.205236654944263e-05]],
            "nfev": 19,
            "mesg": "Both actual and predicted relative reductions in the sum of squares  are at most 0.000000",
            "total_core_cooling_runtime": 52112.304000000004,
            "daily_mean_core_cooling_runtime": 325.7019,
            "core_cooling_days_mean_indoor_temperature": 71.86122395833334,
            "core_cooling_days_mean_outdoor_temperature": 74.372240796875,
            "core_mean_indoor_temperature": 71.86122395833334,
            "core_mean_outdoor_temperature": 74.372240796875,
            "heat_gain_constant": 0.0528959910676605,
            "heat_loss_constant": -0.024651925811247095,
            "hvac_constant": -0.02282666625140404,
            "overall_temperature_variance": 0.8432339920534964,
            "weekly_temperature_variance": 0.21954597415984842,
            "avg_daily_cooling_runtime": 325.7019,
            "avg_daily_heating_runtime": 0.0,
            "avg_daily_auxiliary_runtime": 0.0,
            "avg_daily_emergency_runtime": 0.0,
            "lm_intercept": -8.219240210628417,
            "lm_intercept_se": 0.372868913395607,
            "lm_main_slope": 0.03294502442009115,
            "lm_main_slope_se": 0.0010446404698788295,
            "lm_secondary_slope": nan,
            "lm_secondary_slope_se": nan,
            "lm_cvrmse": 0.005886791963546157,
            "lm_rsquared": 0.8629179431497175,
            "excess_resistance_score_1hr": nan,
            "excess_resistance_score_2hr": nan,
            "excess_resistance_score_3hr": nan,
        },
        {
            "sw_version": "0.1.3",
            "ct_identifier": "c61badb0e0c0a7e06932de804af43111",
            "heat_type": "heat_pump_electric_backup",
            "heat_stage": "two_stage",
            "cool_type": "heat_pump",
            "cool_stage": "two_stage",
            "heating_or_cooling": "heating_ALL",
            "zipcode": "27313",
            "station": "723170",
            "climate_zone": "Mixed-Humid",
            "start_date": "2018-01-01T00:00:00",
            "end_date": "2018-12-31T00:00:00",
            "n_days_in_inputfile_date_range": 364,
            "n_days_both_heating_and_cooling": 17,
            "n_days_insufficient_data": 51,
            "n_core_heating_days": 116,
            "baseline_percentile_core_heating_comfort_temperature": 70.0,
            "regional_average_baseline_heating_comfort_temperature": 69,
            "percent_savings_baseline_percentile": 9.514809890645463,
            "avoided_daily_mean_core_day_runtime_baseline_percentile": 33.69972792209753,
            "avoided_total_core_day_runtime_baseline_percentile": 3909.1684389633133,
            "baseline_daily_mean_core_day_runtime_baseline_percentile": 354.18183137037346,
            "baseline_total_core_day_runtime_baseline_percentile": 41085.09243896332,
            "_daily_mean_core_day_demand_baseline_baseline_percentile": 13.71826955950154,
            "percent_savings_baseline_regional": 3.1471990461144586,
            "avoided_daily_mean_core_day_runtime_baseline_regional": 10.41395767944185,
            "avoided_total_core_day_runtime_baseline_regional": 1208.0190908152547,
            "baseline_daily_mean_core_day_runtime_baseline_regional": 330.89606112771776,
            "baseline_total_core_day_runtime_baseline_regional": 38383.94309081526,
            "_daily_mean_core_day_demand_baseline_baseline_regional": 12.816358606437076,
            "percent_savings_baseline_hourly_regional": -4.893160563800142,
            "avoided_daily_mean_core_day_runtime_baseline_hourly_regional": -14.950168166998818,
            "avoided_total_core_day_runtime_baseline_hourly_regional": -1734.2195073718628,
            "baseline_daily_mean_core_day_runtime_baseline_hourly_regional": 305.531935281277,
            "baseline_total_core_day_runtime_baseline_hourly_regional": 35441.70449262813,
            "_daily_mean_core_day_demand_baseline_baseline_hourly_regional": 11.833948203971415,
            "mean_demand": 12.41300229062868,
            "tau": 13.024414321056941,
            "alpha": 25.818258624686393,
            "mean_sq_err": 6287.039655143009,
            "root_mean_sq_err": 79.2908548014398,
            "cv_root_mean_sq_err": 0.24741117818529584,
            "mean_abs_pct_err": 0.18941422643708195,
            "mean_abs_err": 60.70386971158404,
            "cov_x": [[7.536948763697308e-05]],
            "nfev": 15,
            "mesg": "Both actual and predicted relative reductions in the sum of squares  are at most 0.000000",
            "total_core_heating_runtime": 37175.924000000006,
            "daily_mean_core_heating_runtime": 320.4821034482759,
            "core_heating_days_mean_indoor_temperature": 68.65607040229885,
            "core_heating_days_mean_outdoor_temperature": 43.640953728448274,
            "core_mean_indoor_temperature": 68.65607040229885,
            "core_mean_outdoor_temperature": 43.640953728448274,
            "heat_gain_constant": 0.6405944716697065,
            "heat_loss_constant": -0.0036649329326556234,
            "hvac_constant": -0.001968697650047877,
            "overall_temperature_variance": 0.9840147822568611,
            "weekly_temperature_variance": 0.3322558012005256,
            "avg_daily_cooling_runtime": 0.0,
            "avg_daily_heating_runtime": 320.4821034482759,
            "avg_daily_auxiliary_runtime": 13.039655172413791,
            "avg_daily_emergency_runtime": 0.0,
            "lm_intercept": 13.406925438050902,
            "lm_intercept_se": 0.7695626453749186,
            "lm_main_slope": 0.04012633855590762,
            "lm_main_slope_se": 0.002772064137567037,
            "lm_secondary_slope": 0.03507002072127685,
            "lm_secondary_slope_se": 0.013512589994322892,
            "lm_cvrmse": 0.013011495386856408,
            "lm_rsquared": 0.7640382899823355,
            "excess_resistance_score_1hr": 0.02958600852236783,
            "excess_resistance_score_2hr": 0.03484382424947867,
            "excess_resistance_score_3hr": 0.03630924468102409,
            "total_auxiliary_heating_core_day_runtime": 1512.6000000000001,
            "total_emergency_heating_core_day_runtime": 0.0,
            "dnru_daily": 0.077526531403943,
            "dnru_reduction_daily": 0.26954443613643975,
            "mu_estimate_daily": 23.428022808877056,
            "sigma_estimate_daily": 3.0708466178842206,
            "sigmoid_model_error_daily": 0.00920383100499286,
            "sigmoid_integral_daily": 4.685775428352459,
            "aux_exceeds_heat_runtime_daily": True,
            "dnru_hourly": 0.0466793667182617,
            "dnru_reduction_hourly": 0.33630312696984904,
            "mu_estimate_hourly": 1.9960531212970736,
            "sigma_estimate_hourly": 17.6086700431372,
            "sigmoid_model_error_hourly": 0.0005936031934112763,
            "sigmoid_integral_hourly": 1.6084520686947197,
            "aux_exceeds_heat_runtime_hourly": False,
            "rhu1_00F_to_05F": nan,
            "rhu1_05F_to_10F": nan,
            "rhu1_10F_to_15F": nan,
            "rhu1_15F_to_20F": nan,
            "rhu1_20F_to_25F": 0.5963729624072203,
            "rhu1_25F_to_30F": 0.11484128153249978,
            "rhu1_30F_to_35F": 0.07377455861954366,
            "rhu1_35F_to_40F": 0.04290403220944863,
            "rhu1_40F_to_45F": 0.03502547046482063,
            "rhu1_45F_to_50F": 0.013218695583036512,
            "rhu1_50F_to_55F": 0.0,
            "rhu1_55F_to_60F": 0.014154065085746858,
            "rhu1_30F_to_45F": 0.048018860280357595,
            "rhu2_00F_to_05F": nan,
            "rhu2_05F_to_10F": nan,
            "rhu2_10F_to_15F": nan,
            "rhu2_15F_to_20F": nan,
            "rhu2_20F_to_25F": 0.5963729624072203,
            "rhu2_25F_to_30F": nan,
            "rhu2_30F_to_35F": 0.07377455861954366,
            "rhu2_35F_to_40F": 0.04290403220944863,
            "rhu2_40F_to_45F": 0.03502547046482063,
            "rhu2_45F_to_50F": 0.013218695583036512,
            "rhu2_50F_to_55F": 0.0,
            "rhu2_55F_to_60F": nan,
            "rhu2_30F_to_45F": 0.048018860280357595,
        },
    ]

    return data
