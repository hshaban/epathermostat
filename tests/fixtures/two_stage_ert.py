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
        "../data/two_stage_ert/metadata_furnace_or_boiler_two_stage_central_two_stage.csv"
    ],
)
def thermostat_ert_fu_2_ce_2(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)


@pytest.fixture(
    scope="session",
    params=[
        "../data/two_stage_ert/metadata_furnace_or_boiler_two_stage_none_single_stage.csv"
    ],
)
def thermostat_ert_fu_2_na_1(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)


@pytest.fixture(
    scope="session",
    params=[
        "../data/two_stage_ert/metadata_heat_pump_electric_backup_two_stage_heat_pump_two_stage.csv"
    ],
)
def thermostat_ert_hpeb_2_hp_2(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)


@pytest.fixture(
    scope="session",
    params=["../data/two_stage_ert/metadata_none_two_stage_heat_pump_two_stage.csv"],
)
def thermostat_ert_na_2_hp_2(request):
    thermostats = from_csv(get_data_path(request.param))
    return next(thermostats)


@pytest.fixture(scope="session")
def core_heating_day_set_ert_hpeb_2_hp_2_entire(thermostat_ert_hpeb_2_hp_2):
    return thermostat_ert_hpeb_2_hp_2.get_core_heating_days(method="entire_dataset")[0]


@pytest.fixture(scope="session")
def core_cooling_day_set_ert_hpeb_2_hp_2_entire(thermostat_ert_hpeb_2_hp_2):
    return thermostat_ert_hpeb_2_hp_2.get_core_cooling_days(method="entire_dataset")[0]


@pytest.fixture(scope="session")
def metrics_ert_hpeb_2_hp_2_data():
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
            "n_core_cooling_days": 159,
            "baseline_percentile_core_cooling_comfort_temperature": 70.9,
            "regional_average_baseline_cooling_comfort_temperature": 73.0,
            "percent_savings_baseline_percentile": 7.950071961514231,
            "avoided_daily_mean_core_day_runtime_baseline_percentile": 26.653874266554716,
            "avoided_total_core_day_runtime_baseline_percentile": 4237.9660083822,
            "baseline_daily_mean_core_day_runtime_baseline_percentile": 335.2658239520893,
            "baseline_total_core_day_runtime_baseline_percentile": 53307.2660083822,
            "_daily_mean_core_day_demand_baseline_baseline_percentile": 12.16814778001588,
            "percent_savings_baseline_regional": -9.462987412786953,
            "avoided_daily_mean_core_day_runtime_baseline_regional": -26.67925537512516,
            "avoided_total_core_day_runtime_baseline_regional": -4242.0016046449,
            "baseline_daily_mean_core_day_runtime_baseline_regional": 281.93269431040943,
            "baseline_total_core_day_runtime_baseline_regional": 44827.2983953551,
            "_daily_mean_core_day_demand_baseline_baseline_regional": 10.232473587517678,
            "percent_savings_baseline_hourly_regional": 1.5207727826062385,
            "avoided_daily_mean_core_day_runtime_baseline_hourly_regional": 4.765762960677582,
            "avoided_total_core_day_runtime_baseline_hourly_regional": 757.7563107477356,
            "baseline_daily_mean_core_day_runtime_baseline_hourly_regional": 313.37771264621216,
            "baseline_total_core_day_runtime_baseline_hourly_regional": 49827.056310747736,
            "_daily_mean_core_day_demand_baseline_baseline_hourly_regional": 11.373740017674411,
            "mean_demand": 11.200771275121225,
            "tau": 8.371187895647756,
            "alpha": 27.552740976955135,
            "mean_sq_err": 2714.7353166535677,
            "root_mean_sq_err": 52.103121947284194,
            "cv_root_mean_sq_err": 0.16883053945375592,
            "mean_abs_pct_err": 0.1270126045228687,
            "mean_abs_err": 39.19760751644026,
            "cov_x": [[8.890444749578084e-05]],
            "nfev": 19,
            "mesg": "Both actual and predicted relative reductions in the sum of squares  are at most 0.000000 and the relative error between two consecutive iterates is at   most 0.000000",
            "total_core_cooling_runtime": 49069.3,
            "daily_mean_core_cooling_runtime": 308.6119496855346,
            "core_cooling_days_mean_indoor_temperature": 71.87575995807128,
            "core_cooling_days_mean_outdoor_temperature": 74.44318985849057,
            "core_mean_indoor_temperature": 71.87575995807128,
            "core_mean_outdoor_temperature": 74.44318985849057,
            "heat_gain_constant": 0.05279721300559318,
            "heat_loss_constant": -0.02608637965436161,
            "hvac_constant": -0.019935339745544286,
            "overall_temperature_variance": 0.8188646995078152,
            "weekly_temperature_variance": 0.2112426460503252,
            "avg_daily_cooling_runtime": 308.6119496855346,
            "avg_daily_heating_runtime": 0.0,
            "avg_daily_auxiliary_runtime": 0.0,
            "avg_daily_emergency_runtime": 0.0,
            "lm_intercept": -7.937951369031306,
            "lm_intercept_se": 0.3827627531574688,
            "lm_main_slope": 0.034040746899642836,
            "lm_main_slope_se": 0.0011300821699823218,
            "lm_secondary_slope": nan,
            "lm_secondary_slope_se": nan,
            "lm_cvrmse": 0.006403643666800353,
            "lm_rsquared": 0.8524930786895475,
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
            "percent_savings_baseline_percentile": 9.864369103937042,
            "avoided_daily_mean_core_day_runtime_baseline_percentile": 32.91741702630587,
            "avoided_total_core_day_runtime_baseline_percentile": 3818.4203750514807,
            "baseline_daily_mean_core_day_runtime_baseline_percentile": 333.70017564699555,
            "baseline_total_core_day_runtime_baseline_percentile": 38709.22037505148,
            "_daily_mean_core_day_demand_baseline_baseline_percentile": 13.17555760521648,
            "percent_savings_baseline_regional": 3.3148699002254034,
            "avoided_daily_mean_core_day_runtime_baseline_regional": 10.312399766433282,
            "avoided_total_core_day_runtime_baseline_regional": 1196.2383729062608,
            "baseline_daily_mean_core_day_runtime_baseline_regional": 311.0951583871229,
            "baseline_total_core_day_runtime_baseline_regional": 36087.03837290626,
            "_daily_mean_core_day_demand_baseline_baseline_regional": 12.283038725066332,
            "percent_savings_baseline_hourly_regional": -5.023433690213368,
            "avoided_daily_mean_core_day_runtime_baseline_hourly_regional": -14.386905759978857,
            "avoided_total_core_day_runtime_baseline_hourly_regional": -1668.8810681575474,
            "baseline_daily_mean_core_day_runtime_baseline_hourly_regional": 286.3958528607109,
            "baseline_total_core_day_runtime_baseline_hourly_regional": 33221.91893184246,
            "_daily_mean_core_day_demand_baseline_baseline_hourly_regional": 11.307830599565262,
            "mean_demand": 11.875871971536075,
            "tau": 13.62446309141154,
            "alpha": 25.327214653509362,
            "mean_sq_err": 5950.792154485654,
            "root_mean_sq_err": 77.1413777066864,
            "cv_root_mean_sq_err": 0.2564687486092501,
            "mean_abs_pct_err": 0.1972627612697482,
            "mean_abs_err": 59.3332375078494,
            "cov_x": [[7.669596060995188e-05]],
            "nfev": 15,
            "mesg": "Both actual and predicted relative reductions in the sum of squares  are at most 0.000000 and the relative error between two consecutive iterates is at   most 0.000000",
            "total_core_heating_runtime": 34890.799999999996,
            "daily_mean_core_heating_runtime": 300.7827586206896,
            "core_heating_days_mean_indoor_temperature": 68.65607040229885,
            "core_heating_days_mean_outdoor_temperature": 43.640953728448274,
            "core_mean_indoor_temperature": 68.65607040229885,
            "core_mean_outdoor_temperature": 43.640953728448274,
            "heat_gain_constant": 0.6405944716697065,
            "heat_loss_constant": -0.003685133822820946,
            "hvac_constant": -0.001755439909246502,
            "overall_temperature_variance": 0.9840147822568611,
            "weekly_temperature_variance": 0.3322558012005256,
            "avg_daily_cooling_runtime": 0.0,
            "avg_daily_heating_runtime": 300.7827586206896,
            "avg_daily_auxiliary_runtime": 13.039655172413791,
            "avg_daily_emergency_runtime": 0.0,
            "lm_intercept": 13.714824255989225,
            "lm_intercept_se": 0.7530532639192714,
            "lm_main_slope": 0.041928225597746185,
            "lm_main_slope_se": 0.002905228770085418,
            "lm_secondary_slope": 0.03050906425755245,
            "lm_secondary_slope_se": 0.013718014485862753,
            "lm_cvrmse": 0.013932618395426376,
            "lm_rsquared": 0.763119673726163,
            "excess_resistance_score_1hr": 0.02842258072270436,
            "excess_resistance_score_2hr": 0.032455601547457816,
            "excess_resistance_score_3hr": 0.033785657307496275,
            "total_auxiliary_heating_core_day_runtime": 1512.6000000000001,
            "total_emergency_heating_core_day_runtime": 0.0,
            "dnru_daily": 0.08165462151765186,
            "dnru_reduction_daily": 0.2656491449152059,
            "mu_estimate_daily": 23.50944070120685,
            "sigma_estimate_daily": 3.1154949764320174,
            "sigmoid_model_error_daily": 0.009478437714417857,
            "sigmoid_integral_daily": 4.702030816995914,
            "aux_exceeds_heat_runtime_daily": True,
            "dnru_hourly": 0.049357181761880725,
            "dnru_reduction_hourly": 0.3344944124890115,
            "mu_estimate_hourly": 2.0833950634791125,
            "sigma_estimate_hourly": 17.7352417027378,
            "sigmoid_model_error_hourly": 0.0006156170263438765,
            "sigmoid_integral_hourly": 1.6280028084106708,
            "aux_exceeds_heat_runtime_hourly": False,
            "rhu1_00F_to_05F": nan,
            "rhu1_05F_to_10F": nan,
            "rhu1_10F_to_15F": nan,
            "rhu1_15F_to_20F": nan,
            "rhu1_20F_to_25F": 0.6045587903407809,
            "rhu1_25F_to_30F": 0.12034338820193748,
            "rhu1_30F_to_35F": 0.0771375321534741,
            "rhu1_35F_to_40F": 0.04561882032049096,
            "rhu1_40F_to_45F": 0.03743520199479428,
            "rhu1_45F_to_50F": 0.014363535770523898,
            "rhu1_50F_to_55F": 0.0,
            "rhu1_55F_to_60F": 0.015546218487394958,
            "rhu1_30F_to_45F": 0.050930833104836905,
            "rhu2_00F_to_05F": nan,
            "rhu2_05F_to_10F": nan,
            "rhu2_10F_to_15F": nan,
            "rhu2_15F_to_20F": nan,
            "rhu2_20F_to_25F": 0.6045587903407809,
            "rhu2_25F_to_30F": nan,
            "rhu2_30F_to_35F": 0.0771375321534741,
            "rhu2_35F_to_40F": 0.04561882032049096,
            "rhu2_40F_to_45F": 0.03743520199479428,
            "rhu2_45F_to_50F": 0.014363535770523898,
            "rhu2_50F_to_55F": 0.0,
            "rhu2_55F_to_60F": nan,
            "rhu2_30F_to_45F": 0.050930833104836905,
        },
    ]

    return data
