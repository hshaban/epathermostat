RHU_COLUMNS = [
    "rhu1_00F_to_05F",
    "rhu1_05F_to_10F",
    "rhu1_10F_to_15F",
    "rhu1_15F_to_20F",
    "rhu1_20F_to_25F",
    "rhu1_25F_to_30F",
    "rhu1_30F_to_35F",
    "rhu1_35F_to_40F",
    "rhu1_40F_to_45F",
    "rhu1_45F_to_50F",
    "rhu1_50F_to_55F",
    "rhu1_55F_to_60F",
    "rhu1_30F_to_45F",
    "rhu2_00F_to_05F",
    "rhu2_05F_to_10F",
    "rhu2_10F_to_15F",
    "rhu2_15F_to_20F",
    "rhu2_20F_to_25F",
    "rhu2_25F_to_30F",
    "rhu2_30F_to_35F",
    "rhu2_35F_to_40F",
    "rhu2_40F_to_45F",
    "rhu2_45F_to_50F",
    "rhu2_50F_to_55F",
    "rhu2_55F_to_60F",
    "rhu2_30F_to_45F",
    "dnru_daily",
    "dnru_reduction_daily",
    "mu_estimate_daily",
    "sigma_estimate_daily",
    "sigmoid_model_error_daily",
    "dnru_hourly",
    "dnru_reduction_hourly",
    "mu_estimate_hourly",
    "sigma_estimate_hourly",
    "sigmoid_model_error_hourly",
]

RHU2_IQFLT_COLUMNS = [
    "rhu2IQFLT_00F_to_05F",
    "rhu2IQFLT_05F_to_10F",
    "rhu2IQFLT_10F_to_15F",
    "rhu2IQFLT_15F_to_20F",
    "rhu2IQFLT_20F_to_25F",
    "rhu2IQFLT_25F_to_30F",
    "rhu2IQFLT_30F_to_35F",
    "rhu2IQFLT_35F_to_40F",
    "rhu2IQFLT_40F_to_45F",
    "rhu2IQFLT_45F_to_50F",
    "rhu2IQFLT_50F_to_55F",
    "rhu2IQFLT_55F_to_60F",
    "rhu2IQFLT_30F_to_45F",
]

REAL_OR_INTEGER_VALUED_COLUMNS_HEATING = [
    "n_days_in_inputfile_date_range",
    "n_days_both_heating_and_cooling",
    "n_days_insufficient_data",
    "n_core_heating_days",
    "baseline_percentile_core_heating_comfort_temperature",
    "regional_average_baseline_heating_comfort_temperature",
    "percent_savings_baseline_percentile",
    "avoided_daily_mean_core_day_runtime_baseline_percentile",
    "avoided_total_core_day_runtime_baseline_percentile",
    "baseline_daily_mean_core_day_runtime_baseline_percentile",
    "baseline_total_core_day_runtime_baseline_percentile",
    "_daily_mean_core_day_demand_baseline_baseline_percentile",
    "percent_savings_baseline_regional",
    "avoided_daily_mean_core_day_runtime_baseline_regional",
    "avoided_total_core_day_runtime_baseline_regional",
    "baseline_daily_mean_core_day_runtime_baseline_regional",
    "baseline_total_core_day_runtime_baseline_regional",
    "_daily_mean_core_day_demand_baseline_baseline_regional",
    "percent_savings_baseline_hourly_regional",
    "avoided_daily_mean_core_day_runtime_baseline_hourly_regional",
    "avoided_total_core_day_runtime_baseline_hourly_regional",
    "baseline_daily_mean_core_day_runtime_baseline_hourly_regional",
    "baseline_total_core_day_runtime_baseline_hourly_regional",
    "_daily_mean_core_day_demand_baseline_baseline_hourly_regional",
    "mean_demand",
    "alpha",
    "tau",
    "mean_sq_err",
    "root_mean_sq_err",
    "cv_root_mean_sq_err",
    "mean_abs_err",
    "mean_abs_pct_err",
    "total_core_heating_runtime",
    "total_auxiliary_heating_core_day_runtime",
    "total_emergency_heating_core_day_runtime",
    "daily_mean_core_heating_runtime",
    "core_heating_days_mean_indoor_temperature",
    "core_heating_days_mean_outdoor_temperature",
    "core_mean_indoor_temperature",
    "core_mean_outdoor_temperature",
    "heat_gain_constant",
    "heat_loss_constant",
    "hvac_constant",
] + RHU_COLUMNS

REAL_OR_INTEGER_VALUED_COLUMNS_COOLING = [
    "n_days_in_inputfile_date_range",
    "n_days_both_heating_and_cooling",
    "n_days_insufficient_data",
    "n_core_cooling_days",
    "baseline_percentile_core_cooling_comfort_temperature",
    "regional_average_baseline_cooling_comfort_temperature",
    "percent_savings_baseline_percentile",
    "avoided_daily_mean_core_day_runtime_baseline_percentile",
    "avoided_total_core_day_runtime_baseline_percentile",
    "baseline_daily_mean_core_day_runtime_baseline_percentile",
    "baseline_total_core_day_runtime_baseline_percentile",
    "_daily_mean_core_day_demand_baseline_baseline_percentile",
    "percent_savings_baseline_regional",
    "avoided_daily_mean_core_day_runtime_baseline_regional",
    "avoided_total_core_day_runtime_baseline_regional",
    "baseline_daily_mean_core_day_runtime_baseline_regional",
    "baseline_total_core_day_runtime_baseline_regional",
    "_daily_mean_core_day_demand_baseline_baseline_regional",
    "percent_savings_baseline_hourly_regional",
    "avoided_daily_mean_core_day_runtime_baseline_hourly_regional",
    "avoided_total_core_day_runtime_baseline_hourly_regional",
    "baseline_daily_mean_core_day_runtime_baseline_hourly_regional",
    "baseline_total_core_day_runtime_baseline_hourly_regional",
    "_daily_mean_core_day_demand_baseline_baseline_hourly_regional",
    "mean_demand",
    "alpha",
    "tau",
    "mean_sq_err",
    "root_mean_sq_err",
    "cv_root_mean_sq_err",
    "mean_abs_err",
    "mean_abs_pct_err",
    "total_core_cooling_runtime",
    "daily_mean_core_cooling_runtime",
    "core_cooling_days_mean_indoor_temperature",
    "core_cooling_days_mean_outdoor_temperature",
    "core_mean_indoor_temperature",
    "core_mean_outdoor_temperature",
    "heat_gain_constant",
    "heat_loss_constant",
    "hvac_constant",
]

REAL_OR_INTEGER_VALUED_COLUMNS_ALL = (
    [
        "n_days_in_inputfile_date_range",
        "n_days_both_heating_and_cooling",
        "n_days_insufficient_data",
        "n_core_cooling_days",
        "n_core_heating_days",
        "baseline_percentile_core_cooling_comfort_temperature",
        "baseline_percentile_core_heating_comfort_temperature",
        "regional_average_baseline_cooling_comfort_temperature",
        "regional_average_baseline_heating_comfort_temperature",
        "percent_savings_baseline_percentile",
        "avoided_daily_mean_core_day_runtime_baseline_percentile",
        "avoided_total_core_day_runtime_baseline_percentile",
        "baseline_daily_mean_core_day_runtime_baseline_percentile",
        "baseline_total_core_day_runtime_baseline_percentile",
        "_daily_mean_core_day_demand_baseline_baseline_percentile",
        "percent_savings_baseline_regional",
        "avoided_daily_mean_core_day_runtime_baseline_regional",
        "avoided_total_core_day_runtime_baseline_regional",
        "baseline_daily_mean_core_day_runtime_baseline_regional",
        "baseline_total_core_day_runtime_baseline_regional",
        "_daily_mean_core_day_demand_baseline_baseline_regional",
        "percent_savings_baseline_hourly_regional",
        "avoided_daily_mean_core_day_runtime_baseline_hourly_regional",
        "avoided_total_core_day_runtime_baseline_hourly_regional",
        "baseline_daily_mean_core_day_runtime_baseline_hourly_regional",
        "baseline_total_core_day_runtime_baseline_hourly_regional",
        "_daily_mean_core_day_demand_baseline_baseline_hourly_regional",
        "mean_demand",
        "alpha",
        "tau",
        "mean_sq_err",
        "root_mean_sq_err",
        "cv_root_mean_sq_err",
        "mean_abs_err",
        "mean_abs_pct_err",
        "total_core_cooling_runtime",
        "total_core_heating_runtime",
        "total_auxiliary_heating_core_day_runtime",
        "total_emergency_heating_core_day_runtime",
        "daily_mean_core_cooling_runtime",
        "daily_mean_core_heating_runtime",
        "core_mean_indoor_temperature",
        "core_mean_outdoor_temperature",
        "heat_gain_constant",
        "heat_loss_constant",
        "hvac_constant",
    ]
    + RHU_COLUMNS
    + RHU2_IQFLT_COLUMNS
)

EXPORT_COLUMNS = [
    "sw_version",
    "ct_identifier",
    "heat_type",
    "heat_stage",
    "cool_type",
    "cool_stage",
    "heating_or_cooling",
    "zipcode",
    "station",
    "climate_zone",
    "start_date",
    "end_date",
    "n_days_in_inputfile_date_range",
    "n_days_both_heating_and_cooling",
    "n_days_insufficient_data",
    "n_core_cooling_days",
    "n_core_heating_days",
    "baseline_percentile_core_cooling_comfort_temperature",
    "baseline_percentile_core_heating_comfort_temperature",
    "regional_average_baseline_cooling_comfort_temperature",
    "regional_average_baseline_heating_comfort_temperature",
    "percent_savings_baseline_percentile",
    "avoided_daily_mean_core_day_runtime_baseline_percentile",
    "avoided_total_core_day_runtime_baseline_percentile",
    "baseline_daily_mean_core_day_runtime_baseline_percentile",
    "baseline_total_core_day_runtime_baseline_percentile",
    "_daily_mean_core_day_demand_baseline_baseline_percentile",
    "percent_savings_baseline_regional",
    "avoided_daily_mean_core_day_runtime_baseline_regional",
    "avoided_total_core_day_runtime_baseline_regional",
    "baseline_daily_mean_core_day_runtime_baseline_regional",
    "baseline_total_core_day_runtime_baseline_regional",
    "_daily_mean_core_day_demand_baseline_baseline_regional",
    "percent_savings_baseline_hourly_regional",
    "avoided_daily_mean_core_day_runtime_baseline_hourly_regional",
    "avoided_total_core_day_runtime_baseline_hourly_regional",
    "baseline_daily_mean_core_day_runtime_baseline_hourly_regional",
    "baseline_total_core_day_runtime_baseline_hourly_regional",
    "_daily_mean_core_day_demand_baseline_baseline_hourly_regional",
    "mean_demand",
    "alpha",
    "tau",
    "mean_sq_err",
    "root_mean_sq_err",
    "cv_root_mean_sq_err",
    "mean_abs_err",
    "mean_abs_pct_err",
    "total_core_cooling_runtime",
    "total_core_heating_runtime",
    "total_auxiliary_heating_core_day_runtime",
    "total_emergency_heating_core_day_runtime",
    "daily_mean_core_cooling_runtime",
    "daily_mean_core_heating_runtime",
    "core_cooling_days_mean_indoor_temperature",
    "core_cooling_days_mean_outdoor_temperature",
    "core_heating_days_mean_indoor_temperature",
    "core_heating_days_mean_outdoor_temperature",
    "core_mean_indoor_temperature",
    "core_mean_outdoor_temperature",
    "heat_gain_constant",
    "heat_loss_constant",
    "hvac_constant",
    "aux_exceeds_heat_runtime_daily",
    "aux_exceeds_heat_runtime_hourly",
] + RHU_COLUMNS

CERTIFICATION_HEADERS = [
    "product_id",
    "sw_version",
    "metric",
    "filter",
    "region",
    "statistic",
    "season",
    "value",
]
