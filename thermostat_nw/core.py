from datetime import datetime, timedelta
from collections import namedtuple
import inspect
import warnings
import logging

import pandas as pd
import numpy as np
from scipy.optimize import leastsq, least_squares
from scipy.special import erf
from scipy import integrate
import statsmodels.formula.api as smf

from thermostat_nw import get_version
from thermostat_nw.climate_zone import retrieve_climate_zone
from thermostat_nw.equipment_type import (
    has_heating,
    has_cooling,
    has_auxiliary,
    has_emergency,
    has_resistance_heat,
    validate_heat_type,
    validate_cool_type,
    validate_heat_stage,
    validate_cool_stage,
)

from pkg_resources import resource_stream, resource_exists

warnings.simplefilter("module", Warning)

# Ignore divide-by-zero errors
np.seterr(divide="ignore", invalid="ignore")

CoreDaySet = namedtuple(
    "CoreDaySet", ["name", "daily", "hourly", "start_date", "end_date"]
)

logger = logging.getLogger("epathermostat")

VAR_MIN_RHU_RUNTIME = 30 * 60  # Unit is in minutes (30 hours * 60 minutes)

RESISTANCE_HEAT_USE_BINS_MIN_TEMP = 0  # Unit is 1 degree F.
RESISTANCE_HEAT_USE_BINS_MAX_TEMP = 60  # Unit is 1 degree F.
RESISTANCE_HEAT_USE_BIN_TEMP_WIDTH = 5  # Unit is 1 degree F.
RESISTANCE_HEAT_USE_BIN = list(
    t
    for t in range(
        RESISTANCE_HEAT_USE_BINS_MIN_TEMP,
        RESISTANCE_HEAT_USE_BINS_MAX_TEMP + RESISTANCE_HEAT_USE_BIN_TEMP_WIDTH,
        RESISTANCE_HEAT_USE_BIN_TEMP_WIDTH,
    )
)
RESISTANCE_HEAT_USE_BIN_PAIRS = [
    (RESISTANCE_HEAT_USE_BIN[x], RESISTANCE_HEAT_USE_BIN[x + 1])
    for x in range(0, len(RESISTANCE_HEAT_USE_BIN) - 1)
]

RESISTANCE_HEAT_USE_WIDE_BIN = [30, 45]
RESISTANCE_HEAT_USE_WIDE_BIN_PAIRS = [(30, 45)]

# FIXME: Turning off these warnings for now
pd.set_option("mode.chained_assignment", None)


def __pandas_warnings(pandas_version):
    """ Helper to warn about versions of Pandas that aren't supported yet or have issues """
    try:
        pd_version = pandas_version.split(".")
        pd_major = int(pd_version.pop(0))
        pd_minor = int(pd_version.pop(0))
        if pd_major == 0 and pd_minor == 21:
            warnings.warn(
                "WARNING: Pandas version 0.21.x has known issues and is not supported. "
                "Please upgrade to the Pandas version 0.25.3."
            )
        # Pandas 1.x causes issues. Need to warn about this at the moment.
        if pd_major >= 1:
            warnings.warn(
                "WARNING: Pandas version 1.x has changed significantly, and causes "
                "issues with this software. We are working on supporting Pandas 1.x in "
                "a future release. Please downgrade to Pandas 0.25.3"
            )

    except Exception:
        # If we can't figure out the version string then don't worry about it for now
        return None


try:
    __pandas_warnings(pd.__version__)
except TypeError:
    pass  # Documentation mocks out pd, so ignore if not present.


def avoided(baseline, observed):
    return baseline - observed


def percent_savings(avoided, baseline, thermostat_id):
    savings = np.divide(avoided.mean(), baseline.mean()) * 100.0
    return savings


class Thermostat(object):
    """Main thermostat data container. Each parameter which contains
    timeseries data should be a pandas.Series with a datetimeIndex, and that
    each index should be equivalent.

    Parameters
    ----------
    thermostat_id : object
        An identifier for the thermostat. Can be anything, but should be
        identifying (e.g., an ID provided by the manufacturer).
    heat_type : str
        Name of the Heating Type.
    heat_stage : str
        Name of the Heating Stage.
    cool_type : str
        Name of the Cooling Type.
    cool_stage : str
        Name of the Cooling Stage.
    zipcode : str
        Installation ZIP code for the thermostat.
    station : str
        USAF identifier for weather station used to pull outdoor temperature
        data.
    temperature_in : pandas.Series
        Contains internal temperature data in degrees Fahrenheit (F),
        with resolution of at least 0.5F.
        Should be indexed by a pandas.DatetimeIndex with hourly frequency (i.e.
        :code:`freq='H'`).
    temperature_out : pandas.Series
        Contains outdoor temperature data as observed by a relevant
        weather station in degrees Fahrenheit (F), with resolution of at least
        0.5F.
        Should be indexed by a pandas.DatetimeIndex with hourly frequency (i.e.
        :code:`freq='H'`).
    cool_runtime : pandas.Series,
        Hourly runtimes for cooling equipment controlled by the thermostat,
        measured in minutes. No datapoint should exceed 60 minutes, which would
        indicate over an hour of runtime (impossible).
        Should be indexed by a pandas.DatetimeIndex with hourly frequency (i.e.
        :code:`freq='H'`).
    heat_runtime : pandas.Series,
        Hourly runtimes for heating equipment controlled by the thermostat,
        measured in minutes. No datapoint should exceed 60 minutes, which would
        indicate over an hour of runtime (impossible).
        Should be indexed by a pandas.DatetimeIndex with hourly frequency (i.e.
        :code:`freq='H'`).
    auxiliary_heat_runtime : pandas.Series,
        Hourly runtimes for auxiliary heating equipment controlled by the
        thermostat, measured in minutes. Auxiliary heat runtime is counted when
        both resistance heating and the compressor are running (for heat pump
        systems). No datapoint should exceed 60 minutes, which would indicate
        over a hour of runtime (impossible).
        Should be indexed by a pandas.DatetimeIndex with hourly frequency (i.e.
        :code:`freq='H'`).
    emergency_heat_runtime : pandas.Series,
        Hourly runtimes for emergency heating equipment controlled by the
        thermostat, measured in minutes. Emergency heat runtime is counted when
        resistance heating is running when the compressor is not (for heat pump
        systems). No datapoint should exceed 60 minutes, which would indicate
        over a hour of runtime (impossible).
        Should be indexed by a pandas.DatetimeIndex with hourly frequency (i.e.
        :code:`freq='H'`).
    """

    def __init__(
        self,
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
        emergency_heat_runtime,
    ):

        self.thermostat_id = thermostat_id

        self.heat_type = heat_type
        self.heat_stage = heat_stage
        self.cool_type = cool_type
        self.cool_stage = cool_stage

        self.has_cooling = has_cooling(cool_type)
        self.has_heating = has_heating(heat_type)
        self.has_auxiliary = has_auxiliary(heat_type)
        self.has_emergency = has_emergency(heat_type)
        self.has_resistance_heat = has_resistance_heat(heat_type)

        self.zipcode = zipcode
        self.station = station

        self.temperature_in = self._interpolate(temperature_in, method="linear")
        self.temperature_out = self._interpolate(temperature_out, method="linear")

        self.cool_runtime_hourly = cool_runtime
        self.heat_runtime_hourly = heat_runtime
        if hasattr(cool_runtime, "empty") and cool_runtime.empty is False:
            self.cool_runtime_daily = cool_runtime.resample("D").agg(
                pd.Series.sum, skipna=False
            )
        else:
            self.cool_runtime_daily = pd.Series()
        if hasattr(heat_runtime, "empty") and heat_runtime.empty is False:
            self.heat_runtime_daily = heat_runtime.resample("D").agg(
                pd.Series.sum, skipna=False
            )
        else:
            self.heat_runtime_daily = pd.Series()
        self.auxiliary_heat_runtime = auxiliary_heat_runtime
        self.emergency_heat_runtime = emergency_heat_runtime
        if (
            hasattr(auxiliary_heat_runtime, "empty")
            and auxiliary_heat_runtime.empty is False
        ):
            self.auxiliary_runtime_daily = auxiliary_heat_runtime.resample("D").agg(
                pd.Series.sum, skipna=False
            )
        else:
            self.auxiliary_runtime_daily = pd.Series()
        if (
            hasattr(emergency_heat_runtime, "empty")
            and emergency_heat_runtime.empty is False
        ):
            self.emergency_runtime_daily = emergency_heat_runtime.resample("D").agg(
                pd.Series.sum, skipna=False
            )
        else:
            self.emergency_runtime_daily = pd.Series()

        self.heating_demand = None
        self.tau = None
        self.hourly_temperature_baseline = None
        self.validate()
        self.get_climate_zones()
        self.find_baselines()

    def validate(self):
        # Generate warnings for invalid heating / cooling types and stages
        validate_heat_type(self.heat_type)
        validate_cool_type(self.cool_type)
        validate_heat_stage(self.heat_stage)
        validate_cool_stage(self.cool_stage)

        # Validate the heating, cooling, and aux/emerg settings
        self._validate_heating()
        self._validate_cooling()
        self._validate_aux_emerg()

    def get_climate_zones(self):
        northwest_climate_zone_filename = "northwest_climate_zone_mapping.csv"
        if not resource_exists(
            "thermostat_nw.resources", northwest_climate_zone_filename
        ):
            self.heating_zone_nw = None
            self.cooling_zone_nw = None
            return None
        with resource_stream(
            "thermostat_nw.resources", "northwest_climate_zone_mapping.csv"
        ) as f:
            mapping = pd.read_csv(f, dtype=str)
        try:
            self.heating_zone_nw = mapping.loc[
                mapping.zipcode == self.zipcode, "heating_zone"
            ].iloc[0]
        except IndexError:
            self.heating_zone_nw = None
        try:
            self.cooling_zone_nw = mapping.loc[
                mapping.zipcode == self.zipcode, "cooling_zone"
            ].iloc[0]
        except:
            self.cooling_zone_nw = None

    def find_baselines(self):
        heatpump_baseline_filename = f"heatpump_baseline_nw_hz{self.heating_zone_nw}_cz{self.cooling_zone_nw}.csv"
        if not resource_exists("thermostat_nw.resources", heatpump_baseline_filename):
            heatpump_baseline_filename = "heatpump_baseline_default.csv"
        with resource_stream(
            "thermostat_nw.resources", heatpump_baseline_filename
        ) as f:
            self.runtime_heatpump_baseline = pd.read_csv(f)

        if self.heat_type.startswith("heat_pump"):
            heat_type = "heat_pump"
        else:
            heat_type = self.heat_type
        heat_temperature_baseline_filename = (
            f"temperature_baseline_hz{self.heating_zone_nw}_{heat_type}.csv"
        )
        if not resource_exists(
            "thermostat_nw.resources.temperature_baselines_nw",
            heat_temperature_baseline_filename,
        ):
            heat_temperature_baseline_filename = (
                "temperature_baseline_hz{self.heating_zone_nw}_default.csv"
            )
        if not resource_exists(
            "thermostat_nw.resources.temperature_baselines_nw",
            heat_temperature_baseline_filename,
        ):
            heat_temperature_baseline_filename = "temperature_baseline_default.csv"
        with resource_stream(
            "thermostat_nw.resources.temperature_baselines_nw",
            heat_temperature_baseline_filename,
        ) as f:
            self.hourly_temperature_baseline_heating = pd.read_csv(f)

        cool_temperature_baseline_filename = (
            f"temperature_baseline_cz{self.cooling_zone_nw}_{self.cool_type}.csv"
        )
        if not resource_exists(
            "thermostat_nw.resources.temperature_baselines_nw",
            cool_temperature_baseline_filename,
        ):
            cool_temperature_baseline_filename = (
                "temperature_baseline_cz{self.cooling_zone_nw}_default.csv"
            )
        if not resource_exists(
            "thermostat_nw.resources.temperature_baselines_nw",
            cool_temperature_baseline_filename,
        ):
            cool_temperature_baseline_filename = "temperature_baseline_default.csv"
        with resource_stream(
            "thermostat_nw.resources.temperature_baselines_nw",
            cool_temperature_baseline_filename,
        ) as f:
            self.hourly_temperature_baseline_cooling = pd.read_csv(f)

    def _format_rhu(self, rhu_type, low, high, duty_cycle):
        """Formats the RHU scores for output
        rhu_type : str
            String representation of the RHU type (rhu1, rhu2)
        low : int
            Lower-bound of the RHU bin
        high : int
            Upper-bound of the RHU bin
        duty_cycle : str
            The duty cycle (e.g.: None, 'aux_duty_cycle', 'emg_duty_cycle', 'compressor_duty_cycle')

        Returns
        -------
        result : str
            Formatted string for the RHU type (e.g. 'rhu1_05F_to_10F_aux_duty_cycle')
        """
        format_string = "{rhu_type}_{low:02d}F_to_{high:02d}F"
        if low == -np.inf:
            format_string = "{rhu_type}_less{high:02d}F"
            low = 0  # Don't need this value so we zero it out
        if high == np.inf:
            format_string = "{rhu_type}_greater{low:02d}F"
            high = 0  # Don't need this value so we zero it out

        result = format_string.format(rhu_type=rhu_type, low=int(low), high=int(high))
        if duty_cycle is not None:
            result = "_".join((result, duty_cycle))
        return result

    def _validate_heating(self):
        if self.has_heating:
            if len(self.heat_runtime_daily) == 0:
                message = (
                    "For thermostat {}, heating runtime data was not provided,"
                    " despite equipment type of {}, which requires heating data.".format(
                        self.thermostat_id, self.heat_type
                    )
                )
                raise ValueError(message)

    def _validate_cooling(self):
        if self.has_cooling:
            if len(self.cool_runtime_daily) == 0:
                message = (
                    "For thermostat {}, cooling runtime data was not provided,"
                    " despite equipment type of {}, which requires cooling data.".format(
                        self.thermostat_id, self.cool_type
                    )
                )
                raise ValueError(message)

    def _validate_aux_emerg(self):
        if self.has_auxiliary and self.has_emergency:
            if (
                self.auxiliary_heat_runtime is None
                or self.emergency_heat_runtime is None
            ):
                message = (
                    "For thermostat {}, aux and emergency runtime data were not provided,"
                    " despite heat_type of {}, which requires these columns of data."
                    " If none is available, please change heat_type to 'heat_pump_no_electric_backup',"
                    " or provide columns of 0s".format(
                        self.thermostat_id, self.heat_type
                    )
                )
                raise ValueError(message)

    def _interpolate(self, series, method="linear"):
        if method not in ["linear"]:
            return series
        return series.interpolate(method="linear", limit=1, limit_direction="both")

    def _protect_heating(self):
        function_name = inspect.stack()[1][3]
        if not (self.has_heating):
            message = (
                "The function '{}', which is heating specific, cannot be"
                " called for equipment_type {}".format(function_name, self.heat_type)
            )
            raise ValueError(message)

    def _protect_cooling(self):
        function_name = inspect.stack()[1][3]
        if not (self.has_cooling):
            message = (
                "The function '{}', which is cooling specific, cannot be"
                " called for equipment_type {}".format(function_name, self.cool_type)
            )
            raise ValueError(message)

    def _protect_resistance_heat(self):
        function_name = inspect.stack()[1][3]
        if not (self.has_resistance_heat):
            message = (
                "The function '{}', which is resistance heat specific, cannot be"
                " called for equipment_type {}".format(function_name, self.heat_type)
            )
            raise ValueError(message)

    def _protect_aux_emerg(self):
        function_name = inspect.stack()[1][3]
        if not (self.has_auxiliary and self.has_emergency):
            message = (
                "The function '{}', which is auxiliary/emergency heating specific, cannot be"
                " called for equipment_type {}".format(function_name, self.heat_type)
            )
            raise ValueError(message)

    def get_core_heating_days(
        self, method="entire_dataset", min_minutes_heating=30, max_minutes_cooling=0
    ):
        """Determine core heating days from data associated with this thermostat

        Parameters
        ----------
        method : {"entire_dataset", "year_mid_to_mid"}, default: "entire_dataset"
            Method by which to find core heating day sets.

            - "entire_dataset": all heating days in dataset (days with >= 30 min
              of heating runtime and no cooling runtime. (default)
            - "year_mid_to_mid": groups all heating days (days with >= 30 min
              of total heating and no cooling) from July 1 to June 30
              (inclusive) into individual core heating day sets. May overlap
              with core cooling day sets.
        min_minutes_heating : int, default 30
            Number of minutes of heating runtime per day required for inclusion
            in core heating day set.
        max_minutes_cooling : int, default 0
            Number of minutes of cooling runtime per day beyond which the day
            is considered part of a shoulder season (and is therefore not part
            of the core heating day set).

        Returns
        -------
        core_heating_day_sets : list of thermostat.core.CoreDaySet objects
            List of core day sets detected; Core day sets are represented as
            pandas Series of boolean values, intended to be used as selectors
            or masks on the thermostat data at hourly and daily frequencies.

            A value of True at a particular index indicates inclusion of
            of the data at that index in the core day set. If method is
            "entire_dataset", name of core day sets are "heating_ALL"; if method
            is "year_mid_to_mid", names of core day sets are of the form
            "heating_YYYY-YYYY"
        """

        if method not in ["year_mid_to_mid", "entire_dataset"]:
            raise NotImplementedError

        self._protect_heating()

        # compute inclusion thresholds
        meets_heating_thresholds = self.heat_runtime_daily >= min_minutes_heating

        if self.has_cooling:
            meets_cooling_thresholds = self.cool_runtime_daily <= max_minutes_cooling
        else:
            meets_cooling_thresholds = True

        meets_thresholds = meets_heating_thresholds & meets_cooling_thresholds

        # Determines if enough non-null temperature is present
        # (no more than two missing hours of temperature in / out)
        enough_temp_in = self.temperature_in.groupby(
            self.temperature_in.index.date
        ).apply(lambda x: x.isnull().sum() <= 2)

        enough_temp_out = self.temperature_out.groupby(
            self.temperature_out.index.date
        ).apply(lambda x: x.isnull().sum() <= 2)

        meets_thresholds &= enough_temp_in & enough_temp_out

        data_start_date = np.datetime64(self.heat_runtime_daily.index[0])
        data_end_date = np.datetime64(self.heat_runtime_daily.index[-1])

        if method == "year_mid_to_mid":
            # find all potential core heating day ranges
            start_year = data_start_date.item().year - 1
            end_year = data_end_date.item().year + 1
            potential_core_day_sets = zip(
                range(start_year, end_year), range(start_year + 1, end_year + 1)
            )

            # for each potential core day set, look for core heating days.
            core_heating_day_sets = []
            for start_year_, end_year_ in potential_core_day_sets:
                core_day_set_start_date = np.datetime64(datetime(start_year_, 7, 1))
                core_day_set_end_date = np.datetime64(datetime(end_year_, 7, 1))
                start_date = max(core_day_set_start_date, data_start_date).item()
                end_date = min(core_day_set_end_date, data_end_date).item()
                in_range = self._get_range_boolean(
                    self.heat_runtime_daily.index, start_date, end_date
                )
                inclusion_daily = pd.Series(
                    in_range & meets_thresholds, index=self.heat_runtime_daily.index
                )

                if any(inclusion_daily):
                    name = "heating_{}-{}".format(start_year_, end_year_)
                    inclusion_hourly = self._get_hourly_boolean(inclusion_daily)
                    core_day_set = CoreDaySet(
                        name, inclusion_daily, inclusion_hourly, start_date, end_date
                    )
                    core_heating_day_sets.append(core_day_set)

            return core_heating_day_sets

        elif method == "entire_dataset":
            inclusion_daily = pd.Series(
                meets_thresholds, index=self.heat_runtime_daily.index
            )
            inclusion_hourly = self._get_hourly_boolean(inclusion_daily)
            core_heating_day_set = CoreDaySet(
                "heating_ALL",
                inclusion_daily,
                inclusion_hourly,
                data_start_date,
                data_end_date,
            )
            # returned as list for consistency
            core_heating_day_sets = [core_heating_day_set]
            return core_heating_day_sets

    def get_core_cooling_days(
        self, method="entire_dataset", min_minutes_cooling=30, max_minutes_heating=0
    ):
        """Determine core cooling days from data associated with this
        thermostat.

        Parameters
        ----------
        method : {"entire_dataset", "year_end_to_end"}, default: "entire_dataset"
            Method by which to find core cooling days.

            - "entire_dataset": all cooling days in dataset (days with >= 30 min
              of cooling runtime and no heating runtime.
            - "year_end_to_end": groups all cooling days (days with >= 30 min
              of total cooling and no heating) from January 1 to December 31
              into individual core cooling sets.
        min_minutes_cooling : int, default 30
            Number of minutes of core cooling runtime per day required for
            inclusion in core cooling day set.
        max_minutes_heating : int, default 0
            Number of minutes of heating runtime per day beyond which the day is
            considered part of a shoulder season (and is therefore not part of
            the core cooling day set).

        Returns
        -------
        core_cooling_day_sets : list of thermostat.core.CoreDaySet objects
            List of core day sets detected; Core day sets are represented as
            pandas Series of boolean values, intended to be used as selectors
            or masks on the thermostat data at hourly and daily frequencies.

            A value of True at a particular index indicates inclusion of
            of the data at that index in the core day set. If method is
            "entire_dataset", name of core day set is "cooling_ALL"; if method
            is "year_end_to_end", names of core day sets are of the form
            "cooling_YYYY"
        """
        if method not in ["year_end_to_end", "entire_dataset"]:
            raise NotImplementedError

        self._protect_cooling()

        # find all potential core cooling day ranges
        data_start_date = np.datetime64(self.cool_runtime_daily.index[0])
        data_end_date = np.datetime64(self.cool_runtime_daily.index[-1])

        # compute inclusion thresholds
        if self.has_heating:
            meets_heating_thresholds = self.heat_runtime_daily <= max_minutes_heating
        else:
            meets_heating_thresholds = True

        meets_cooling_thresholds = self.cool_runtime_daily >= min_minutes_cooling
        meets_thresholds = meets_heating_thresholds & meets_cooling_thresholds

        # enough temperature_in
        enough_temp_in = self.temperature_in.groupby(
            self.temperature_in.index.date
        ).apply(lambda x: x.isnull().sum() <= 2)

        enough_temp_out = self.temperature_out.groupby(
            self.temperature_out.index.date
        ).apply(lambda x: x.isnull().sum() <= 2)

        meets_thresholds &= enough_temp_in & enough_temp_out

        if method == "year_end_to_end":
            start_year = data_start_date.item().year
            end_year = data_end_date.item().year
            potential_core_day_sets = range(start_year, end_year + 1)

            # for each potential core day set, look for cooling days.
            core_cooling_day_sets = []
            for year in potential_core_day_sets:
                core_day_set_start_date = np.datetime64(datetime(year, 1, 1))
                core_day_set_end_date = np.datetime64(datetime(year + 1, 1, 1))
                start_date = max(core_day_set_start_date, data_start_date).item()
                end_date = min(core_day_set_end_date, data_end_date).item()
                in_range = self._get_range_boolean(
                    self.cool_runtime_daily.index, start_date, end_date
                )
                inclusion_daily = pd.Series(
                    in_range & meets_thresholds, index=self.cool_runtime_daily.index
                )

                if any(inclusion_daily):
                    name = "cooling_{}".format(year)
                    inclusion_hourly = self._get_hourly_boolean(inclusion_daily)
                    core_day_set = CoreDaySet(
                        name, inclusion_daily, inclusion_hourly, start_date, end_date
                    )
                    core_cooling_day_sets.append(core_day_set)

            return core_cooling_day_sets
        elif method == "entire_dataset":
            inclusion_daily = pd.Series(
                meets_thresholds, index=self.cool_runtime_daily.index
            )
            inclusion_hourly = self._get_hourly_boolean(inclusion_daily)
            core_day_set = CoreDaySet(
                "cooling_ALL",
                inclusion_daily,
                inclusion_hourly,
                data_start_date,
                data_end_date,
            )
            core_cooling_day_sets = [core_day_set]
            return core_cooling_day_sets

    def _get_range_boolean(self, dt_index, start_date, end_date):
        after_start = dt_index >= start_date
        before_end = dt_index < end_date
        return after_start & before_end

    def _get_hourly_boolean(self, daily_boolean):
        values = np.repeat(daily_boolean.values, 24)
        index = pd.date_range(
            start=daily_boolean.index[0],
            periods=daily_boolean.index.shape[0] * 24,
            freq="H",
        )
        hourly_boolean = pd.Series(values, index)
        return hourly_boolean

    def total_heating_runtime(self, core_day_set):
        """Calculates total heating runtime.

        Parameters
        ----------
        core_day_set : thermostat.core.CoreDaySet
            Core day set for which to calculate total runtime.

        Returns
        -------
        total_runtime : float
            Total heating runtime.
        """
        self._protect_heating()
        return self.heat_runtime_daily[core_day_set.daily].sum()

    def total_auxiliary_heating_runtime(self, core_day_set):
        """Calculates total auxiliary heating runtime.

        Parameters
        ----------
        core_day_set : thermostat.core.CoreDaySet
            Core day set for which to calculate total runtime.

        Returns
        -------
        total_runtime : float
            Total auxiliary heating runtime.
        """
        self._protect_aux_emerg()
        return self.auxiliary_heat_runtime[core_day_set.hourly].sum()

    def total_emergency_heating_runtime(self, core_day_set):
        """Calculates total emergency heating runtime.

        Parameters
        ----------
        core_day_set : thermostat.core.CoreDaySet
            Core day set for which to calculate total runtime.

        Returns
        -------
        total_runtime : float
            Total heating runtime.
        """
        self._protect_aux_emerg()
        return self.emergency_heat_runtime[core_day_set.hourly].sum()

    def total_cooling_runtime(self, core_day_set):
        """Calculates total cooling runtime.

        Parameters
        ----------
        core_day_set : thermostat.core.CoreDaySet
            Core day set for which to calculate total runtime.

        Returns
        -------
        total_runtime : float
            Total cooling runtime.
        """
        self._protect_cooling()
        return self.cool_runtime_daily[core_day_set.daily].sum()

    def get_resistance_heat_utilization_runtime(self, core_heating_day_set):
        """Calculates resistance heat utilization runtime and filters based on
        the core heating days

        Parameters
        ----------
        core_heating_day_set : thermostat.core.CoreDaySet
            Core heating day set for which to calculate total runtime.

        Returns
        -------
        runtime_temp : pandas.DataFrame or None
            A pandas DataFrame which includes the outdoor temperature, heat
            runtime, aux runtime, and emergency runtime, filtered by the core
            heating day set. Returns None if the thermostat does
            not control the appropriate equipment.
        """

        self._protect_aux_emerg()
        self._protect_resistance_heat()

        in_core_day_set_daily = self._get_range_boolean(
            core_heating_day_set.daily.index,
            core_heating_day_set.start_date,
            core_heating_day_set.end_date,
        )

        # convert hourly to daily
        temp_out_daily = self.temperature_out.resample("D").mean()
        aux_daily = self.auxiliary_heat_runtime.resample("D").sum()
        emg_daily = self.emergency_heat_runtime.resample("D").sum()

        # Build the initial DataFrame based on daily readings
        runtime_temp_daily = pd.DataFrame()
        runtime_temp_daily["temperature"] = temp_out_daily
        runtime_temp_daily["heat_runtime"] = self.heat_runtime_daily
        runtime_temp_daily["aux_runtime"] = aux_daily
        runtime_temp_daily["emg_runtime"] = emg_daily
        runtime_temp_daily["in_core_daily"] = in_core_day_set_daily
        runtime_temp_daily["total_minutes"] = 1440  # default number of minutes per day

        # Filter out records that aren't part of the core day set
        runtime_temp_daily = runtime_temp_daily[
            runtime_temp_daily["in_core_daily"].map(lambda x: x is True)
        ]

        return runtime_temp_daily

    def get_resistance_heat_utilization_bins(
        self, runtime_temp, bins, core_heating_day_set, min_runtime_minutes=None
    ):
        """Calculates the resistance heat utilization in
        bins (provided by the bins parameter)

        Parameters
        ----------
        runtime_temp: DataFrame
            Runtime Temperatures Dataframe from get_resistance_heat_utilization_runtime
        bins : list
            List of the bins (rightmost-edge aligned) for binning
        core_heating_day_set : thermostat.core.CoreDaySet
            Core heating day set for which to calculate total runtime.

        Returns
        -------
        RHUs : pandas.DataFrame or None
            Resistance heat utilization for each temperature bin, ordered
            ascending by temperature bin. Returns None if the thermostat does
            not control the appropriate equipment or if the runtime_temp is None.
        """
        self._protect_resistance_heat()
        self._protect_aux_emerg()

        if runtime_temp is None:
            return None

        # Create the bins and group by them
        runtime_temp["bins"] = pd.cut(runtime_temp["temperature"], bins)
        runtime_rhu = runtime_temp.groupby("bins")[
            "heat_runtime", "aux_runtime", "emg_runtime", "total_minutes"
        ].sum()

        # Calculate the RHU based on the bins
        runtime_rhu["rhu"] = (
            runtime_rhu["aux_runtime"] + runtime_rhu["emg_runtime"]
        ) / (runtime_rhu["heat_runtime"] + runtime_rhu["emg_runtime"])

        # Currently treating aux_runtime as separate from heat_runtime
        runtime_rhu["total_runtime"] = (
            runtime_rhu.heat_runtime + runtime_rhu.aux_runtime + runtime_rhu.emg_runtime
        )

        # If we're passed min_runtime_minutes (RHU2) then treat the thermostat as not having run during that period
        if min_runtime_minutes:
            runtime_rhu["rhu"].loc[
                runtime_rhu.total_runtime < min_runtime_minutes
            ] = np.nan
            runtime_rhu["total_runtime"].loc[
                runtime_rhu.total_runtime < min_runtime_minutes
            ] = np.nan

        runtime_rhu["data_is_nonsense"] = (
            runtime_rhu["aux_runtime"] > runtime_rhu["heat_runtime"]
        )
        runtime_rhu.loc[
            runtime_rhu.data_is_nonsense == True, "rhu"
        ] = np.nan  # noqa: E712

        if runtime_rhu.data_is_nonsense.any():
            for item in runtime_rhu.itertuples():
                if item.data_is_nonsense:
                    warnings.warn(
                        "WARNING: "
                        "aux heat runtime %s > compressor runtime %s "
                        "for %sF <= temperature < %sF "
                        "for thermostat_id %s "
                        "from %s to %s inclusive"
                        % (
                            item.aux_runtime,
                            item.heat_runtime,
                            item.Index.left,
                            item.Index.right,
                            self.thermostat_id,
                            core_heating_day_set.start_date,
                            core_heating_day_set.end_date,
                        )
                    )

        return runtime_rhu

    def get_ignored_days(self, core_day_set):
        """Determine how many days are ignored for a particular core day set

        Returns
        -------

        n_both : int
            Number of days excluded from core day set because of presence of
            both heating and cooling runtime.
        n_days_insufficient : int
            Number of days excluded from core day set because of null runtime
            data.
        """

        in_range = self._get_range_boolean(
            core_day_set.daily.index, core_day_set.start_date, core_day_set.end_date
        )

        if self.has_heating:
            has_heating = self.heat_runtime_daily > 0
            null_heating = pd.isnull(self.heat_runtime_daily)
        else:
            has_heating = False
            null_heating = False  # shouldn't be counted, so False, not True

        if self.has_cooling:
            has_cooling = self.cool_runtime_daily > 0
            null_cooling = pd.isnull(self.cool_runtime_daily)
        else:
            has_cooling = False
            null_cooling = False  # shouldn't be counted, so False, not True

        n_both = (in_range & has_heating & has_cooling).sum()
        n_days_insufficient = (in_range & (null_heating | null_cooling)).sum()
        return n_both, n_days_insufficient

    def get_core_day_set_n_days(self, core_day_set):
        """Returns number of days in the core day set."""
        return int(core_day_set.daily.sum())

    def get_inputfile_date_range(self, core_day_set):
        """Returns number of days of data provided in input data file."""
        delta = core_day_set.end_date - core_day_set.start_date
        if isinstance(delta, timedelta):
            return delta.days
        return int(delta.astype("timedelta64[D]") / np.timedelta64(1, "D"))

    def get_cooling_demand(self, core_cooling_day_set):
        """
        Calculates a measure of cooling demand using the hourlyavgCTD method.

        Starting with an assumed value of zero for Tau :math:`(\\tau_c)`,
        calculate the daily Cooling Thermal Demand :math:`(\\text{daily CTD}_d)`, as follows

        :math:`\\text{daily CTD}_d = \\frac{\\sum_{i=1}^{24} [\\tau_c - \\text{hourly} \\Delta T_{d.n}]_{+}}{24}`, where

        :math:`\\text{hourly} \\Delta T_{d.n} (^{\\circ} F) = \\text{hourly indoor} T_{d.n} - \\text{hourly outdoor} T_{d.n}`, and

        :math:`d` is the core cooling day; :math:`\\left(001, 002, 003 ... x \\right)`,

        :math:`n` is the hour; :math:`\\left(01, 02, 03 ... 24 \\right)`,

        :math:`\\tau_c` (cooling) is the :math:`\\Delta T` associated with :math:`CTD=0` (zero cooling runtime), and

        :math:`[]_{+}` indicates that the term is zero if its value would be negative.

        For the set of all core cooling days in the CT interval data file, use
        ratio estimation to calculate :math:`\\alpha_c`, the home's
        responsiveness to cooling, which should be positive.

        :math:`\\alpha_c \\left(\\frac{\\text{minutes}}{^{\\circ} F}\\right) = \\frac{RT_\\text{actual cool}}{\\sum_{d=1}^{x} \\text{daily CTD}_d}`, where

        :math:`RT_\\text{actual cool}` is the sum of cooling run times for all core cooling days in the CT interval data file.

        For the set of all core cooling days in the CT interval data file,
        optimize :math:`\\tau_c` that results in minimization of the sum of
        squares of the difference between daily run times reported by the CT,
        and calculated daily cooling run times.

        Next recalculate :math:`\\alpha_c` (in accordance with the above step)
        and record the model's parameters :math:`\\left(\\alpha_c, \\tau_c \\right)`

        Parameters
        ----------
        core_cooling_day_set : thermostat.core.CoreDaySet
            Core day set over which to calculate cooling demand.

        Returns
        -------
        demand : pd.Series
            Daily demand in the core heating day set as calculated using the
            method described above.
        tau : float
            Estimate of :math:`\\tau_c`.
        alpha : float
            Estimate of :math:`\\alpha_c`
        mse : float
            Mean squared error in runtime estimates.
        rmse : float
            Root mean squared error in runtime estimates.
        cvrmse : float
            Coefficient of variation of root mean squared error in runtime estimates.
        mape : float
            Mean absolute percent error
        mae : float
            Mean absolute error
        """

        self._protect_cooling()

        core_day_set_temp_in = self.temperature_in[core_cooling_day_set.hourly]
        core_day_set_temp_out = self.temperature_out[core_cooling_day_set.hourly]
        core_day_set_deltaT = core_day_set_temp_in - core_day_set_temp_out

        daily_index = core_cooling_day_set.daily[core_cooling_day_set.daily].index

        def calc_cdd(tau):
            hourly_cdd = (tau - core_day_set_deltaT).apply(lambda x: np.maximum(x, 0))
            # Note - `x / 24` this should be thought of as a unit conversion, not an average.
            return np.array(
                [
                    cdd.sum() / 24
                    for day, cdd in hourly_cdd.groupby(core_day_set_deltaT.index.date)
                ]
            )

        daily_runtime = self.cool_runtime_daily[core_cooling_day_set.daily]
        total_runtime = daily_runtime.sum()

        def calc_estimates(tau):
            cdd = calc_cdd(tau)
            total_cdd = np.sum(cdd)
            if total_cdd != 0.0:
                alpha_estimate = total_runtime / total_cdd
            else:
                alpha_estimate = np.nan
                logger.debug(
                    "Alpha Estimate divided by zero: %s / %s"
                    "for thermostat %s" % (total_runtime, total_cdd, self.thermostat_id)
                )
            runtime_estimate = cdd * alpha_estimate
            errors = daily_runtime - runtime_estimate
            return cdd, alpha_estimate, errors

        def estimate_errors(tau_estimate):
            _, _, errors = calc_estimates(tau_estimate)
            return errors

        tau_starting_guess = 0
        try:
            y = leastsq(estimate_errors, tau_starting_guess, full_output=1)
        except TypeError:  # len 0
            assert (
                daily_runtime.shape[0] == 0
            )  # make sure no other type errors are sneaking in
            return (
                pd.Series([], index=daily_index, dtype="Float64"),
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
            )

        tau_estimate = y[0][0]

        cdd, alpha_estimate, errors = calc_estimates(tau_estimate)
        mse = np.nanmean((errors) ** 2)
        rmse = mse ** 0.5
        mean_daily_runtime = np.nanmean(daily_runtime)

        if y[1] is not None:
            cov_x = y[1].tolist()
        else:
            cov_x = [[]]
        nfev = y[2]["nfev"]
        mesg = y[3].replace("\n", "")
        try:
            cvrmse = rmse / mean_daily_runtime
        except ZeroDivisionError:
            logger.debug(
                "CVRMSE divided by zero: %s / %s "
                "for thermostat_id %s " % (rmse, mean_daily_runtime, self.thermostat_id)
            )
            cvrmse = np.nan

        mape = np.nanmean(np.absolute(errors / mean_daily_runtime))
        mae = np.nanmean(np.absolute(errors))

        return (
            pd.Series(cdd, index=daily_index),
            tau_estimate,
            alpha_estimate,
            mse,
            rmse,
            cvrmse,
            mape,
            mae,
            cov_x,
            nfev,
            mesg,
        )

    def get_heating_demand(self, core_heating_day_set):
        """
        Calculates a measure of heating demand using the hourlyavgCTD method.

        :math:`\\text{daily HTD}_d = \\frac{\\sum_{i=1}^{24} [\\text{hourly} \\Delta T_{d.n} - \\tau_h]_{+}}{24}`, where

        :math:`\\text{hourly} \\Delta T_{d.n} (^{\\circ} F) = \\text{hourly indoor} T_{d.n} - \\text{hourly outdoor} T_{d.n}`, and

        :math:`d` is the core heating day; :math:`\\left(001, 002, 003 ... x \\right)`,

        :math:`n` is the hour; :math:`\\left(01, 02, 03 ... 24 \\right)`,

        :math:`\\tau_h` (heating) is the :math:`\\Delta T` associated with :math:`HTD=0`, reflecting that homes with no heat running tend to be warmer \
        that the outdoors, and

        :math:`[]_{+}` indicates that the term is zero if its value would be negative.

        For the set of all core heating days in the CT interval data file, use
        ratio estimation to calculate :math:`\\alpha_h`, the home's
        responsiveness to heating, which should be positive.

        :math:`\\alpha_h \\left(\\frac{\\text{minutes}}{^{\\circ} F}\\right) = \\frac{RT_\\text{actual heat}}{\\sum_{d=1}^{x} \\text{daily HTD}_d}`, where

        :math:`RT_\\text{actual heat}` is the sum of heating run times for all core heating days in the CT interval data file.

        For the set of all core heating days in the CT interval data file,
        optimize :math:`\\tau_h` that results in minimization of the sum of
        squares of the difference between daily run times reported by the CT,
        and calculated daily heating run times.

        Next recalculate :math:`\\alpha_h` (in accordance with the above step)
        and record the model's parameters :math:`\\left(\\alpha_h, \\tau_h \\right)`

        Parameters
        ----------
        core_heating_day_set : array_like
            Core day set over which to calculate heating demand.

        Returns
        -------
        demand : pd.Series
            Daily demand in the core heating day set as calculated using the
            method described above.
        tau : float
            Estimate of :math:`\\tau_h`.
        alpha : float
            Estimate of :math:`\\alpha_h`
        mse : float
            Mean squared error in runtime estimates.
        rmse : float
            Root mean squared error in runtime estimates.
        cvrmse : float
            Coefficient of variation of root mean squared error in runtime estimates.
        mape : float
            Mean absolute percent error
        mae : float
            Mean absolute error
        """

        self._protect_heating()

        core_day_set_temp_in = self.temperature_in[core_heating_day_set.hourly]
        core_day_set_temp_out = self.temperature_out[core_heating_day_set.hourly]
        core_day_set_deltaT = core_day_set_temp_in - core_day_set_temp_out

        daily_index = core_heating_day_set.daily[core_heating_day_set.daily].index

        def calc_hdd(tau):
            hourly_hdd = (core_day_set_deltaT - tau).apply(lambda x: np.maximum(x, 0))
            # Note - this `x / 24` should be thought of as a unit conversion, not an average.
            return np.array(
                [
                    hdd.sum() / 24
                    for day, hdd in hourly_hdd.groupby(core_day_set_deltaT.index.date)
                ]
            )

        daily_runtime = self.heat_runtime_daily[core_heating_day_set.daily]
        total_runtime = daily_runtime.sum()

        def calc_estimates(tau):
            hdd = calc_hdd(tau)
            total_hdd = np.sum(hdd)
            if total_hdd != 0.0:
                alpha_estimate = total_runtime / total_hdd
            else:
                alpha_estimate = np.nan
                logger.debug(
                    "alpha_estimate divided by zero: %s / %s "
                    "for thermostat_id %s "
                    % (total_runtime, total_hdd, self.thermostat_id)
                )
            runtime_estimate = hdd * alpha_estimate
            errors = daily_runtime - runtime_estimate
            return hdd, alpha_estimate, errors

        def estimate_errors(tau_estimate):
            _, _, errors = calc_estimates(tau_estimate)
            return errors

        tau_starting_guess = 0

        try:
            y = leastsq(estimate_errors, tau_starting_guess, full_output=1)
        except TypeError:  # len 0
            assert (
                daily_runtime.shape[0] == 0
            )  # make sure no other type errors are sneaking in
            return (
                pd.Series([], index=daily_index, dtype="Float64"),
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
            )

        tau_estimate = y[0][0]

        hdd, alpha_estimate, errors = calc_estimates(tau_estimate)
        mse = np.nanmean((errors) ** 2)
        rmse = mse ** 0.5
        mean_daily_runtime = np.nanmean(daily_runtime)
        if y[1] is not None:
            cov_x = y[1].tolist()
        else:
            cov_x = [[]]
        nfev = y[2]["nfev"]
        mesg = y[3].replace("\n", "")
        try:
            cvrmse = rmse / mean_daily_runtime
        except ZeroDivisionError:
            logger.debug(
                "CVRMSE divided by zero: %s / %s "
                "for thermostat_id %s " % (rmse, mean_daily_runtime, self.thermostat_id)
            )
            cvrmse = np.nan

        mape = np.nanmean(np.absolute(errors / mean_daily_runtime))
        mae = np.nanmean(np.absolute(errors))

        return (
            pd.Series(hdd, index=daily_index),
            tau_estimate,
            alpha_estimate,
            mse,
            rmse,
            cvrmse,
            mape,
            mae,
            cov_x,
            nfev,
            mesg,
        )

    def get_core_cooling_day_baseline_setpoint(
        self, core_cooling_day_set, method="tenth_percentile", source="temperature_in"
    ):
        """Calculate the core cooling day baseline setpoint (comfort
        temperature).

        Parameters
        ----------
        core_cooling_day_set : thermost.core.CoreDaySet
            Core cooling days over which to calculate baseline cooling setpoint.
        method : {"tenth_percentile"}, default: "tenth_percentile"
            Method to use in calculation of the baseline.

            - "tenth_percentile": 10th percentile of source temperature.
              (temperature in).
        source : {"temperature_in"}, default "temperature_in"
            The source of temperatures to use in baseline calculation.

        Returns
        -------
        baseline : float
            The baseline cooling setpoint for the core cooling days as determined
            by the given method.
        """

        self._protect_cooling()

        if method == "tenth_percentile" and source == "temperature_in":
            return (
                self.temperature_in[core_cooling_day_set.hourly].dropna().quantile(0.1)
            )

        if source == "cooling_setpoint":
            warnings.warn("Cooling Setpoint method is no longer implemented.")

        # For everything else, return "Not Implemented"
        raise NotImplementedError

    def get_core_heating_day_baseline_setpoint(
        self,
        core_heating_day_set,
        method="ninetieth_percentile",
        source="temperature_in",
    ):
        """Calculate the core heating day baseline setpoint (comfort temperature).

        Parameters
        ----------
        core_heating_day_set : thermostat.core.CoreDaySet
            Core heating days over which to calculate baseline heating setpoint.
        method : {"ninetieth_percentile"}, default: "ninetieth_percentile"
            Method to use in calculation of the baseline.

            - "ninetieth_percentile": 90th percentile of source temperature.
              (indoor temperature).
        source : {"temperature_in"}, default "temperature_in"
            The source of temperatures to use in baseline calculation.

        Returns
        -------
        baseline : float
            The baseline heating setpoint for the heating day as determined
            by the given method.
        """

        self._protect_heating()

        if method == "ninetieth_percentile" and source == "temperature_in":
            return (
                self.temperature_in[core_heating_day_set.hourly].dropna().quantile(0.9)
            )

        if source == "heating_setpoint":
            warnings.warn("Heating setpoint method is no longer implemented")

        # For everything else, return "Not Implemented"
        raise NotImplementedError

    def get_baseline_cooling_demand(self, core_cooling_day_set, temp_baseline, tau):
        """Calculate baseline cooling demand for a particular core cooling
        day set and fitted physical parameters.

        :math:`\\text{daily CTD base}_d = \\frac{\\sum_{i=1}^{24} [\\tau_c - \\text{hourly } \\Delta T \\text{ base cool}_{d.n}]_{+}}{24}`, where

        :math:`\\text{hourly } \\Delta T \\text{ base cool}_{d.n} (^{\\circ} F) = \\text{base heat} T_{d.n} - \\text{hourly outdoor} T_{d.n}`, and

        :math:`d` is the core cooling day; :math:`\\left(001, 002, 003 ... x \\right)`,

        :math:`n` is the hour; :math:`\\left(01, 02, 03 ... 24 \\right)`,

        :math:`\\tau_c` (cooling), determined earlier, is a constant that is part of the CT/home's thermal/HVAC cooling run time model, and

        :math:`[]_{+}` indicates that the term is zero if its value would be negative.

        Parameters
        ----------
        core_cooling_day_set : thermostat.core.CoreDaySet
            Core cooling days over which to calculate baseline cooling demand.
        temp_baseline : float
            Baseline comfort temperature
        tau : float, default: None
            From fitted demand model.

        Returns
        -------
        baseline_cooling_demand : pandas.Series
            A series containing baseline daily heating demand for the core
            cooling day set.
        """
        self._protect_cooling()

        hourly_temp_out = self.temperature_out[core_cooling_day_set.hourly]

        hourly_cdd = (tau - (temp_baseline - hourly_temp_out)).apply(
            lambda x: np.maximum(x, 0)
        )
        demand = np.array(
            [
                cdd.sum() / 24
                for day, cdd in hourly_cdd.groupby(hourly_temp_out.index.date)
            ]
        )

        index = core_cooling_day_set.daily[core_cooling_day_set.daily].index
        return pd.Series(demand, index=index)

    def get_baseline_heating_demand(self, core_heating_day_set, temp_baseline, tau):
        """Calculate baseline heating demand for a particular core heating day
        set and fitted physical parameters.

        :math:`\\text{daily HTD base}_d = \\frac{\\sum_{i=1}^{24} [\\text{hourly } \\Delta T \\text{ base heat}_{d.n} - \\tau_h]_{+}}{24}`, where

        :math:`\\text{hourly } \\Delta T \\text{ base heat}_{d.n} (^{\\circ} F) = \\text{base cool} T_{d.n} - \\text{hourly outdoor} T_{d.n}`, and

        :math:`d` is the core heating day; :math:`\\left(001, 002, 003 ... x \\right)`,

        :math:`n` is the hour; :math:`\\left(01, 02, 03 ... 24 \\right)`,

        :math:`\\tau_h` (heating), determined earlier, is a constant that is part of the CT/home's thermal/HVAC heating run time model, and

        :math:`[]_{+}` indicates that the term is zero if its value would be negative.

        Parameters
        ----------
        core_heating_day_set : thermostat.core.CoreDaySet
            Core heating days over which to calculate baseline heating demand.
        temp_baseline : float
            Baseline comfort temperature
        tau : float, default: None
            From fitted demand model.

        Returns
        -------
        baseline_heating_demand : pandas.Series
            A series containing baseline daily heating demand for the core heating days.
        """
        self._protect_heating()

        hourly_temp_out = self.temperature_out[core_heating_day_set.hourly]

        hourly_hdd = (temp_baseline - hourly_temp_out - tau).apply(
            lambda x: np.maximum(x, 0)
        )
        demand = np.array(
            [
                hdd.sum() / 24
                for day, hdd in hourly_hdd.groupby(hourly_temp_out.index.date)
            ]
        )

        index = core_heating_day_set.daily[core_heating_day_set.daily].index
        return pd.Series(demand, index=index)

    def get_baseline_cooling_runtime(self, baseline_cooling_demand, alpha):
        """Calculate baseline cooling runtime given baseline cooling demand
        and fitted physical parameters.

        :math:`RT_{\\text{base cool}} (\\text{minutes}) = \\alpha_c \\cdot \\text{daily CTD base}_d`

        Parameters
        ----------
        baseline_cooling_demand : pandas.Series
            A series containing estimated daily baseline cooling demand.
        alpha : float
            Slope of fitted line

        Returns
        -------
        baseline_cooling_runtime : pandas.Series
            A series containing estimated daily baseline cooling runtime.
        """
        return np.maximum(alpha * (baseline_cooling_demand), 0)

    def get_baseline_heating_runtime(self, baseline_heating_demand, alpha):
        """Calculate baseline heating runtime given baseline heating demand.
        and fitted physical parameters.

        :math:`RT_{\\text{base heat}} (\\text{minutes}) = \\alpha_h \\cdot \\text{daily HTD base}_d`

        Parameters
        ----------
        baseline_heating_demand : pandas.Series
            A series containing estimated daily baseline heating demand.
        alpha : float
            Slope of fitted line

        Returns
        -------
        baseline_heating_runtime : pandas.Series
            A series containing estimated daily baseline heating runtime.
        """
        return np.maximum(alpha * (baseline_heating_demand), 0)

    def get_temperature_constants(self, core_day_set):
        """NWMOD: Calculate the temperature constant for a specific day set.

        Returns
        -------
        heat_gain_constant : float
            Value of heat gain constant for this core day set.
        heat_loss_constant : float
            Value of heat loss constant for this core day set.
        """
        # Error handling if heating or cooling runtime is missing
        if not self.has_cooling:
            cool_runtime_hourly = pd.Series(
                [0] * len(self.temperature_out.index), index=self.temperature_out.index
            )
        else:
            cool_runtime_hourly = self.cool_runtime_hourly
        if not self.has_heating:
            heat_runtime_hourly = pd.Series(
                [0] * len(self.temperature_out.index), index=self.temperature_out.index
            )
        else:
            heat_runtime_hourly = self.heat_runtime_hourly
        # Create a dataframe with four columns: heating/cooling runtime and indoor/outdoor temperatures
        df = pd.concat(
            [
                cool_runtime_hourly,
                heat_runtime_hourly,
                self.temperature_in,
                self.temperature_out,
            ],
            axis=1,
        )
        df.columns = ["cool_runtime", "heat_runtime", "temp_in", "temp_out"]

        # Calculate a new column - the temperature gradient. The difference between indoor
        # temperature in this hour minus the previous hour divided by the indoor-outdoor
        # temperature difference in this hour
        df["temp_gradient"] = (df.loc[:, "temp_in"] - df.shift(1).loc[:, "temp_in"]) / (
            (df.loc[:, "temp_out"] - df.loc[:, "temp_in"]).map(
                lambda x: 0.1 if abs(x) < 0.1 else x
            )
        )
        # Heat gain constant is the mean temperature gradient with minimal heating/cooling
        # and with the outdoor temperature larger than the indoor temperature
        heat_gain_constant = (
            df.loc[core_day_set.hourly]
            .loc[
                (df.heat_runtime <= 5)
                & (df.cool_runtime <= 5)
                & ((df.temp_out - df.temp_in) > 1)
            ]
            .temp_gradient.mean()
        )
        # Heat loss constant is the mean temperature gradient with minimal heating/cooling
        # and with the indoor temperature larger than the outdoor temperature
        heat_loss_constant = (
            df.loc[core_day_set.hourly]
            .loc[
                (df.heat_runtime <= 5)
                & (df.cool_runtime <= 5)
                & ((df.temp_in - df.temp_out) > 1)
            ]
            .temp_gradient.mean()
        )
        return heat_gain_constant, heat_loss_constant

    def get_temperature_variance(self, core_day_set):
        """NWMOD: Calculate the temperature variance for a specific day set.

        Returns
        -------
        overall_temperature_variance : float
            Standard deviation of indoor temperatures for this core day set.
        weekly_temperature_variance : float
            Standard deviation of indoor temperatures for this core day set grouped by hour of week.
        """
        # Generate a dataframe with indoor temperature, hour of day, hour of week and day of week
        df = pd.DataFrame(self.temperature_in)
        if len(df.index) == 0:
            return np.nan, np.nan
        df["hour_of_day"] = df.index.hour
        df["day_of_week"] = df.index.weekday
        df["hour_of_week"] = df.day_of_week * 24 + df.hour_of_day

        # Filter by core day set
        df = df.loc[core_day_set.hourly]
        # Group by hour of week and take the mean
        df_grouped = df.groupby("hour_of_week").agg({"temp_in": np.mean})

        return df.temp_in.std(), df_grouped.temp_in.std()

    def get_cooling_hvac_constant(self, core_day_set):
        """NWMOD: Calculate the HVAC time constant for a specific day set.

        Returns
        -------
        cooling_hvac_constant : float
            Value of HVAC time constant for this core day set.
        """
        self._protect_cooling()

        # Generate a dataframe with cooling runtime, and indoor/outdoor temperatures
        df = pd.concat(
            [self.cool_runtime_hourly, self.temperature_in, self.temperature_out],
            axis=1,
        )
        df.columns = ["cool_runtime", "temp_in", "temp_out"]

        # Calculate a new column - the temperature gradient. The difference between indoor
        # temperature in this hour minus the prvious hour divided by the indoor-outdoor
        # temperature difference in this hour
        df["temp_gradient"] = (
            (df.loc[:, "temp_in"] - df.shift(1).loc[:, "temp_in"])
            / (
                (df.loc[:, "temp_out"] - df.loc[:, "temp_in"]).map(
                    lambda x: 0.1 if abs(x) < 0.1 else x
                )
            )
            / df.cool_runtime.map(lambda x: 0.1 if abs(x) < 0.1 else x)
            * 60
        )

        # Cooling HVAC constant is the mean temperature gradient with cooling runtime over 15 minutes
        # and with the outdoor temperature larger than the indoor temperature
        cooling_hvac_constant = (
            df.loc[core_day_set.hourly]
            .loc[(df.cool_runtime >= 15) & ((df.temp_out - df.temp_in) > 1)]
            .temp_gradient.mean()
        )
        return cooling_hvac_constant

    def get_heating_hvac_constant(self, core_day_set):
        """NWMOD: Calculate the HVAC time constant for a specific day set.

        Returns
        -------
        heating_hvac_constant : float
            Value of HVAC time constant for this core day set.
        """
        self._protect_heating()

        # Generate a dataframe with cooling runtime, and indoor/outdoor temperatures
        df = pd.concat(
            [self.heat_runtime_hourly, self.temperature_in, self.temperature_out],
            axis=1,
        )
        df.columns = ["heat_runtime", "temp_in", "temp_out"]

        # Calculate a new column - the temperature gradient. The difference between indoor
        # temperature in this hour minus the prvious hour divided by the indoor-outdoor
        # temperature difference in this hour
        df["temp_gradient"] = (
            (df.loc[:, "temp_in"] - df.shift(1).loc[:, "temp_in"])
            / (
                (df.loc[:, "temp_out"] - df.loc[:, "temp_in"]).map(
                    lambda x: 0.1 if abs(x) < 0.1 else x
                )
            )
            / df.heat_runtime.map(lambda x: 0.1 if abs(x) < 0.1 else x)
            * 60
        )

        # Heating HVAC constant is the mean temperature gradient with heating runtime over 15 minutes
        # and with the indoor temperature larger than the outdoor temperature
        heating_hvac_constant = (
            df.loc[core_day_set.hourly]
            .loc[(df.heat_runtime >= 15) & ((df.temp_in - df.temp_out) > 1)]
            .temp_gradient.mean()
        )
        return heating_hvac_constant

    def fit_sigmoid_model(self, runtime_rhu, n_points_threshold=2):
        """NWMOD: Calculate sigmoid function parameters for resistance heat utilization.
        0.5 * (1 - erf((temperatures - mu) / (sigma * np.sqrt(2))))

        Parameters
        ----------
        runtime_rhu : pandas.DataFrame
            A dataframe containing resistance heating utilization grouped by temperature bins.
        n_points_threshold : int
            Data quality filter.

        Returns
        -------
        mu_estimate : float
            Estimate of the mean parameter of the sigmoid function.
        sigma_estimate : float
            Estimate of the st. deviation parameter of the sigmoid function.
        sigmoid_model_error : float
            Estimate of the mean squared error of the sigmoid function fit.
        sigmoid_integral : float
            Integral of the sigmoid function between the smallest and
            largest temperature bins (0-60F by default).
        """
        # Function to optimize
        def calc_estimates(parameters, runtime_rhu):
            mu = parameters[0]
            sigma = parameters[1]
            # Drop temperature bins that have little or no data
            rhu = runtime_rhu.dropna()
            rhu = rhu.loc[rhu.n_points > n_points_threshold]
            # Get temperature value from temperature bins
            temperatures = pd.Series([x.mid for x in rhu.index])
            # Calculate the sigmoid function and associated errors.
            function_fit = 0.5 * (1 - erf((temperatures - mu) / (sigma * np.sqrt(2))))
            errors = (function_fit.values - rhu.rhu.values) ** 2
            return np.sqrt(np.sum(errors) / np.sum(rhu.n_points))

        initial_parameters = [30, 5]
        try:
            # Do the least squares optimization on the sigmoid function
            y = least_squares(
                calc_estimates, initial_parameters, kwargs={"runtime_rhu": runtime_rhu}
            )
            mu_estimate = y.x[0]
            sigma_estimate = y.x[1]
            sigmoid_model_error = calc_estimates(y.x, runtime_rhu)
            # Calculate the estimated sigmiod function over all bins and integrate
            runtime_rhu["estimated_rhu"] = 0.5 * (
                1
                - erf(
                    ([x.mid for x in runtime_rhu.index] - mu_estimate)
                    / (sigma_estimate * np.sqrt(2))
                )
            )
            sigmoid_integral = np.sum(runtime_rhu.estimated_rhu)
        except:
            mu_estimate = None
            sigma_estimate = None
            sigmoid_model_error = None
            sigmoid_integral = None

        return mu_estimate, sigma_estimate, sigmoid_model_error, sigmoid_integral

    def fit_linear_cooling_model(self, core_day_set):
        """NWMOD: Calculate an OLS model between indoor-outdoor temperature
        delta and runtime

        Parameters
        ----------
        core_day_set : thermostat.core.CoreDaySet
            Core cooling days over which to calculate baseline cooling demand.

        Returns
        -------
        model_parameters : float
            Model parameters.
        model_se : float
            Standard errors of model parameters.
        model_fit_metrics : float
            R-squared and CVRMSE of OLS model.
        excess_resistance_scores : float
            Scores calculated over 1, 2 and 3 hr rolling windows.
        """
        self._protect_cooling()

        df_daily = self.get_delta_df_cooling(core_day_set)
        if df_daily.shape[0] == 0:
            return (
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
                np.nan,
            )
        model = smf.ols(formula="temperature_delta ~ cool_runtime", data=df_daily)

        rsquared = model.fit().rsquared
        intercept = model.fit().params["Intercept"]
        intercept_se = model.fit().bse["Intercept"]
        cool_slope = model.fit().params["cool_runtime"]
        cool_slope_se = model.fit().bse["cool_runtime"]
        resistance_slope = np.nan
        resistance_slope_se = np.nan
        mse = np.nanmean((model.fit().resid) ** 2)
        rmse = mse ** 0.5
        mean_daily_runtime = np.nanmean(df_daily.cool_runtime)

        try:
            cvrmse = rmse / mean_daily_runtime
        except ZeroDivisionError:
            logger.debug(
                "CVRMSE divided by zero: %s / %s "
                "for thermostat_id %s " % (rmse, mean_daily_runtime, self.thermostat_id)
            )
            cvrmse = np.nan

        excess_resistance_score_1hr = np.nan
        excess_resistance_score_2hr = np.nan
        excess_resistance_score_3hr = np.nan
        return (
            intercept,
            intercept_se,
            cool_slope,
            cool_slope_se,
            resistance_slope,
            resistance_slope_se,
            cvrmse,
            rsquared,
            excess_resistance_score_1hr,
            excess_resistance_score_2hr,
            excess_resistance_score_3hr,
        )

    def get_delta_df_cooling(self, core_day_set):
        """NWMOD: return a daily dataframe of temperature delta and runtime"""
        self._protect_cooling()

        df = pd.DataFrame()
        df["temperature_out"] = self.temperature_out
        df["temperature_in"] = self.temperature_in
        df["temperature_delta"] = df.temperature_out - df.temperature_in
        df["cool_runtime"] = self.cool_runtime_hourly

        df_daily = df.resample("D").agg(
            {"temperature_delta": np.mean, "cool_runtime": np.sum}
        )
        df_daily = df_daily[core_day_set.daily]
        return df_daily.loc[:, ["temperature_delta", "cool_runtime"]]

    def fit_linear_heating_model(self, core_day_set):
        self._protect_heating()

        if self.has_auxiliary:
            df_daily = self.get_delta_df_heatpump(core_day_set)
            if df_daily.shape[0] == 0:
                return (
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                )
            model = smf.ols(
                formula="temperature_delta ~ adjusted_heat_runtime + resistance_runtime",
                data=df_daily,
            )
            resistance_slope = model.fit().params["resistance_runtime"]
            resistance_slope_se = model.fit().bse["resistance_runtime"]
            heat_slope = model.fit().params["adjusted_heat_runtime"]
            heat_slope_se = model.fit().bse["adjusted_heat_runtime"]
            mean_daily_runtime = np.nanmean(df_daily.adjusted_heat_runtime)

            (
                excess_resistance_score_1hr,
                excess_resistance_score_2hr,
                excess_resistance_score_3hr,
            ) = self.get_excess_resistance_scores(
                core_day_set, heat_slope, resistance_slope
            )

        else:
            df_daily = self.get_delta_df_furnace(core_day_set)
            if df_daily.shape[0] == 0:
                return (
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                )
            model = smf.ols(formula="temperature_delta ~ heat_runtime", data=df_daily)
            resistance_slope = np.nan
            resistance_slope_se = np.nan
            heat_slope = model.fit().params["heat_runtime"]
            heat_slope_se = model.fit().bse["heat_runtime"]
            mean_daily_runtime = np.nanmean(df_daily.heat_runtime)
            excess_resistance_score_1hr = np.nan
            excess_resistance_score_2hr = np.nan
            excess_resistance_score_3hr = np.nan

        rsquared = model.fit().rsquared
        intercept = model.fit().params["Intercept"]
        intercept_se = model.fit().bse["Intercept"]
        mse = np.nanmean((model.fit().resid) ** 2)
        rmse = mse ** 0.5

        try:
            cvrmse = rmse / mean_daily_runtime
        except ZeroDivisionError:
            logger.debug(
                "CVRMSE divided by zero: %s / %s "
                "for thermostat_id %s " % (rmse, mean_daily_runtime, self.thermostat_id)
            )
            cvrmse = np.nan

        return (
            intercept,
            intercept_se,
            heat_slope,
            heat_slope_se,
            resistance_slope,
            resistance_slope_se,
            cvrmse,
            rsquared,
            excess_resistance_score_1hr,
            excess_resistance_score_2hr,
            excess_resistance_score_3hr,
        )

    def get_delta_df_furnace(self, core_day_set):
        self._protect_heating()

        df = pd.DataFrame()
        df["temperature_out"] = self.temperature_out
        df["temperature_in"] = self.temperature_in
        df["temperature_delta"] = df.temperature_in - df.temperature_out
        df["heat_runtime"] = self.heat_runtime_hourly

        df_daily = df.resample("D").agg(
            {"temperature_delta": np.mean, "heat_runtime": np.sum}
        )
        df_daily = df_daily[core_day_set.daily]

        return df_daily.loc[:, ["temperature_delta", "heat_runtime"]]

    def get_delta_df_heatpump(self, core_day_set):
        self._protect_heating()

        df = pd.DataFrame()
        df["temperature_out"] = self.temperature_out
        df["temperature_in"] = self.temperature_in
        df["temperature_delta"] = df.temperature_in - df.temperature_out
        df["heat_runtime"] = self.heat_runtime_hourly
        df["adjusted_heat_runtime"] = df.heat_runtime * (
            1 - 0.012 * (47 - df.temperature_out)
        )
        df["resistance_runtime"] = (
            self.auxiliary_heat_runtime + self.emergency_heat_runtime
        )

        df_daily = df.resample("D").agg(
            {
                "temperature_delta": np.mean,
                "adjusted_heat_runtime": np.sum,
                "resistance_runtime": np.sum,
            }
        )
        df_daily = df_daily[core_day_set.daily]

        return df_daily.loc[
            :,
            [
                "temperature_delta",
                "heat_runtime",
                "adjusted_heat_runtime",
                "resistance_runtime",
            ],
        ]

    def get_excess_resistance_scores(self, core_day_set, heat_slope, resistance_slope):
        self._protect_resistance_heat()
        self._protect_aux_emerg()

        df = pd.DataFrame()
        df["temperature_out"] = self.temperature_out
        df["temperature_in"] = self.temperature_in
        df["temperature_delta"] = df.temperature_in - df.temperature_out
        df["heat_runtime"] = self.heat_runtime_hourly
        df["adjusted_heat_runtime"] = df.heat_runtime * (
            1 - 0.012 * (47 - df.temperature_out)
        )
        df["full_heat_runtime"] = 60 * (1 - 0.012 * (47 - df.temperature_out))

        df["available_compressor_runtime"] = (
            df.full_heat_runtime - df.adjusted_heat_runtime
        )
        df["available_compressor_runtime_nm1"] = df.available_compressor_runtime.shift(
            1
        )
        df["available_compressor_runtime_nm2"] = df.available_compressor_runtime.shift(
            2
        )

        df["resistance_runtime"] = (
            self.auxiliary_heat_runtime + self.emergency_heat_runtime
        )
        df["resistance_runtime_nm1"] = df.resistance_runtime.shift(1)
        df["resistance_runtime_nm2"] = df.resistance_runtime.shift(2)

        df = df[core_day_set.hourly]

        df["excess_resistance_1hr"] = df.apply(
            lambda x: min(
                x.resistance_runtime * resistance_slope,
                x.available_compressor_runtime * heat_slope,
            ),
            axis=1,
        )
        df["excess_resistance_2hr"] = df.apply(
            lambda x: min(
                (x.resistance_runtime + x.resistance_runtime_nm1) * resistance_slope,
                (x.available_compressor_runtime + x.available_compressor_runtime_nm1)
                * heat_slope,
            )
            / 2,
            axis=1,
        )
        df["excess_resistance_3hr"] = df.apply(
            lambda x: min(
                (
                    x.resistance_runtime
                    + x.resistance_runtime_nm1
                    + x.resistance_runtime_nm2
                )
                * resistance_slope,
                (
                    x.available_compressor_runtime
                    + x.available_compressor_runtime_nm1
                    + x.available_compressor_runtime_nm2
                )
                * heat_slope,
            )
            / 3,
            axis=1,
        )

        excess_resistance_score_1hr = df.excess_resistance_1hr.sum() / (
            (df.resistance_runtime * resistance_slope).sum()
            + (df.adjusted_heat_runtime * heat_slope).sum()
        )
        excess_resistance_score_2hr = df.excess_resistance_2hr.sum() / (
            (df.resistance_runtime * resistance_slope).sum()
            + (df.adjusted_heat_runtime * heat_slope).sum()
        )
        excess_resistance_score_3hr = df.excess_resistance_3hr.sum() / (
            (df.resistance_runtime * resistance_slope).sum()
            + (df.adjusted_heat_runtime * heat_slope).sum()
        )

        return (
            excess_resistance_score_1hr,
            excess_resistance_score_2hr,
            excess_resistance_score_3hr,
        )

    def get_binned_demand_daily(self, demand, bins):
        """NWMOD: Create a binned dataframe for thermal demand.

        Parameters
        ----------
        demand : pandas.DataFrame
            A dataframe containing a timeseries of daily thermal demand.
        bins : list
            List of bin endpoints for resistance heat utilization calculations.

        Returns
        -------
        binned_demand : pandas.DataFrame
            A dataframe containing a timeseries of thermal demand and temperature bin.
        """
        self._protect_resistance_heat()
        self._protect_aux_emerg()

        if demand is None:
            return None
        elif type(demand) == pd.Series:
            demand = pd.DataFrame(demand).rename(columns={0: "demand"})
            temperature = pd.DataFrame(
                self.temperature_out.resample("D").agg(np.mean)
            ).rename(columns={0: "temperature_out"})
        # Merge the demand df with outdoor temperature by timestamp
        df = demand.merge(temperature, left_index=True, right_index=True)

        # Create the bins and group by them
        df["bins"] = pd.cut(df.temperature_out, bins)
        return df

    def get_rh_metrics_daily(self, bins, core_day_set):
        """NWMOD: Calculate resistance heat utilization metrics using daily data.

        Returns
        -------
        rh_metrics : dict
            Dictionary of resistance heat metrics
        """
        self._protect_resistance_heat()
        self._protect_aux_emerg()

        # Get resistance heat runtime timeseries and bin by outdoor temperature
        runtime_temp = self.get_resistance_heat_utilization_runtime(core_day_set)
        runtime_temp["n_points"] = 1
        runtime_temp["bins"] = pd.cut(runtime_temp["temperature"], bins)
        runtime_rhu = runtime_temp.groupby("bins")[
            "heat_runtime", "aux_runtime", "emg_runtime", "n_points"
        ].sum()
        # Calculate the resistance heat utilization in every temperature bin
        runtime_rhu["rhu"] = (
            runtime_rhu["aux_runtime"] + runtime_rhu["emg_runtime"]
        ) / (runtime_rhu["heat_runtime"] + runtime_rhu["emg_runtime"])

        # Error catching for empty dataframes
        if (self.heating_demand is None) | (len(runtime_rhu.dropna().index) == 0):
            return {
                "dnru_daily": np.nan,
                "dnru_reduction_daily": np.nan,
                "mu_estimate_daily": np.nan,
                "sigma_estimate_daily": np.nan,
                "sigmoid_model_error_daily": np.nan,
                "sigmoid_integral_daily": np.nan,
                "aux_exceeds_heat_runtime_daily": np.nan,
            }
        if len(self.heating_demand) == 0:
            return {
                "dnru_daily": np.nan,
                "dnru_reduction_daily": np.nan,
                "mu_estimate_daily": np.nan,
                "sigma_estimate_daily": np.nan,
                "sigmoid_model_error_daily": np.nan,
                "sigmoid_integral_daily": np.nan,
                "aux_exceeds_heat_runtime_daily": np.nan,
            }
        # Merge demand timeseries with resistance heat utilization on
        # outdoor temperature bin
        binned_demand = self.get_binned_demand_daily(self.heating_demand, bins)
        binned_demand = binned_demand.merge(
            runtime_rhu.loc[:, "rhu"], left_on="bins", right_index=True
        )
        # Get the weighted average resistance heat utilization
        binned_demand["rhu_norm"] = binned_demand.demand * binned_demand.rhu
        dnru_daily = binned_demand.rhu_norm.sum() / binned_demand.demand.sum()

        # Get the baseline resistance heat runtime and assign temperature bins
        runtime_temp_baseline = self.runtime_heatpump_baseline.groupby(
            "day_of_year"
        ).agg(
            {
                "temperature": np.mean,
                "heat_runtime": np.sum,
                "aux_runtime": np.sum,
                "emg_runtime": np.sum,
            }
        )
        runtime_temp_baseline["bins"] = pd.cut(
            runtime_temp_baseline["temperature"], bins
        )
        runtime_rhu_baseline = runtime_temp_baseline.groupby("bins")[
            "heat_runtime", "aux_runtime", "emg_runtime"
        ].sum()
        # Calculate resistance heat utilization
        runtime_rhu_baseline["rhu_baseline"] = (
            runtime_rhu_baseline["aux_runtime"] + runtime_rhu_baseline["emg_runtime"]
        ) / (
            runtime_rhu_baseline["heat_runtime"]
            + runtime_rhu_baseline["emg_runtime"]
            + 0.00001
        )
        # Merge demand timeseries with resistance heat utilization on
        # outdoor temperature bin
        binned_demand = binned_demand.merge(
            runtime_rhu_baseline.loc[:, "rhu_baseline"],
            left_on="bins",
            right_index=True,
        )
        # Get the demand normalized difference in resistance heat utilization and
        # calculate the weighted average
        binned_demand["rhu_norm_reduction"] = binned_demand.demand * (
            binned_demand.rhu_baseline - binned_demand.rhu
        )
        dnru_reduction_daily = (
            binned_demand.rhu_norm_reduction.sum() / binned_demand.demand.sum()
        )

        # Get the sigmoid model outputs
        (
            mu_estimate,
            sigma_estimate,
            sigmoid_model_error,
            sigmoid_integral,
        ) = self.fit_sigmoid_model(runtime_rhu)

        return {
            "dnru_daily": dnru_daily,
            "dnru_reduction_daily": dnru_reduction_daily,
            "mu_estimate_daily": mu_estimate,
            "sigma_estimate_daily": sigma_estimate,
            "sigmoid_model_error_daily": sigmoid_model_error,
            "sigmoid_integral_daily": sigmoid_integral,
            "aux_exceeds_heat_runtime_daily": any(
                runtime_rhu.aux_runtime > runtime_rhu.heat_runtime
            ),
        }

    def get_binned_demand_hourly(self, bins):
        """NWMOD: Create a binned dataframe for thermal demand.

        Parameters
        ----------
        demand : pandas.DataFrame
            A dataframe containing a timeseries of hourly thermal demand.
        bins : list
            List of bin endpoints for resistance heat utilization calculations.

        Returns
        -------
        binned_demand : pandas.DataFrame
            A dataframe containing a timeseries of thermal demand and temperature bin.
        """
        self._protect_resistance_heat()
        self._protect_aux_emerg()

        demand = (self.temperature_in - self.temperature_out - self.tau).apply(
            lambda x: np.maximum(x, 0)
        )
        demand = pd.DataFrame(demand).rename(columns={0: "demand"})
        temperature = pd.DataFrame(self.temperature_out).rename(
            columns={0: "temperature"}
        )
        # Merge the demand df with outdoor temperature by timestamp
        df = demand.merge(temperature, left_index=True, right_index=True)

        # Create the bins and group by them
        df["bins"] = pd.cut(df.temperature, bins)
        return df

    def get_rh_metrics_hourly(self, bins, core_day_set):
        """NWMOD: Calculate resistance heat utilization metrics using hourly data.

        Returns
        -------
        rh_metrics : dict
            Dictionary of resistance heat metrics
        """
        self._protect_resistance_heat()
        self._protect_aux_emerg()

        # Build a resistance heat runtime timeseries and bin by outdoor temperature
        runtime_temp = pd.DataFrame()
        runtime_temp["temperature"] = self.temperature_out
        runtime_temp["heat_runtime"] = self.heat_runtime_hourly
        runtime_temp["aux_runtime"] = self.auxiliary_heat_runtime
        runtime_temp["emg_runtime"] = self.emergency_heat_runtime
        runtime_temp["n_points"] = 1
        runtime_temp["bins"] = pd.cut(runtime_temp["temperature"], bins)
        runtime_temp = runtime_temp[core_day_set.hourly]

        # Calculate the resistance heat utilization in every temperature bin
        runtime_rhu = runtime_temp.groupby("bins")[
            "heat_runtime", "aux_runtime", "emg_runtime", "n_points"
        ].sum()
        runtime_rhu["rhu"] = (
            runtime_rhu["aux_runtime"] + runtime_rhu["emg_runtime"]
        ) / (runtime_rhu["heat_runtime"] + runtime_rhu["emg_runtime"])

        # Error catching for empty dataframes
        if len(runtime_rhu.dropna().index) == 0:
            return {
                "dnru_hourly": np.nan,
                "dnru_reduction_hourly": np.nan,
                "mu_estimate_hourly": np.nan,
                "sigma_estimate_hourly": np.nan,
                "sigmoid_model_error_hourly": np.nan,
                "sigmoid_integral_hourly": np.nan,
                "aux_exceeds_heat_runtime_hourly": np.nan,
            }
        if len(self.heating_demand) == 0:
            return {
                "dnru_hourly": np.nan,
                "dnru_reduction_hourly": np.nan,
                "mu_estimate_hourly": np.nan,
                "sigma_estimate_hourly": np.nan,
                "sigmoid_model_error_hourly": np.nan,
                "sigmoid_integral_hourly": np.nan,
                "aux_exceeds_heat_runtime_hourly": np.nan,
            }

        # Merge demand timeseries with resistance heat utilization on
        # outdoor temperature bin
        binned_demand = self.get_binned_demand_hourly(bins)
        binned_demand = binned_demand.merge(
            runtime_rhu.loc[:, "rhu"], left_on="bins", right_index=True
        )
        # Get the weighted average resistance heat utilization
        binned_demand["rhu_norm"] = binned_demand.demand * binned_demand.rhu
        dnru_hourly = binned_demand.rhu_norm.sum() / binned_demand.demand.sum()

        # Get the baseline resistance heat runtime and assign temperature bins
        runtime_temp_baseline = self.runtime_heatpump_baseline
        runtime_temp_baseline["bins"] = pd.cut(
            runtime_temp_baseline["temperature"], bins
        )
        runtime_rhu_baseline = runtime_temp_baseline.groupby("bins")[
            "heat_runtime", "aux_runtime", "emg_runtime"
        ].sum()
        # Calculate resistance heat utilization
        runtime_rhu_baseline["rhu_baseline"] = (
            runtime_rhu_baseline["aux_runtime"] + runtime_rhu_baseline["emg_runtime"]
        ) / (
            runtime_rhu_baseline["heat_runtime"]
            + runtime_rhu_baseline["emg_runtime"]
            + 0.00001
        )
        # Merge demand timeseries with resistance heat utilization on
        # outdoor temperature bin
        binned_demand = binned_demand.merge(
            runtime_rhu_baseline.loc[:, "rhu_baseline"],
            left_on="bins",
            right_index=True,
        )
        # Get the demand normalized difference in resistance heat utilization and
        # calculate the weighted average
        binned_demand["rhu_norm_reduction"] = binned_demand.demand * (
            binned_demand.rhu_baseline - binned_demand.rhu
        )
        dnru_reduction_hourly = (
            binned_demand.rhu_norm_reduction.sum() / binned_demand.demand.sum()
        )

        # Get the sigmoid model outputs
        (
            mu_estimate,
            sigma_estimate,
            sigmoid_model_error,
            sigmoid_integral,
        ) = self.fit_sigmoid_model(runtime_rhu, 48)

        return {
            "dnru_hourly": dnru_hourly,
            "dnru_reduction_hourly": dnru_reduction_hourly,
            "mu_estimate_hourly": mu_estimate,
            "sigma_estimate_hourly": sigma_estimate,
            "sigmoid_model_error_hourly": sigmoid_model_error,
            "sigmoid_integral_hourly": sigmoid_integral,
            "aux_exceeds_heat_runtime_hourly": any(
                runtime_rhu.aux_runtime > runtime_rhu.heat_runtime
            ),
        }

    def get_baseline_hourly_cooling_demand(
        self, core_cooling_day_set, temp_baseline, tau
    ):
        """NWMOD: Calculate baseline cooling demand using a regional baseline.

        Returns
        -------
        baseline_hourly_demand : pd.Series
            Timeseries of daily demand using a regional baseline
        """
        self._protect_cooling()

        # Get the outdoor temperature for this core day set
        hourly_temp_out = self.temperature_out[core_cooling_day_set.hourly]
        if len(hourly_temp_out) == 0:
            return pd.Series()

        # Build a dataframe of outdoor temperature and merge it with the
        # baseline temperature timeseries
        df = pd.DataFrame()
        df["temperature_out"] = hourly_temp_out
        df.index = hourly_temp_out.index
        df["leap_adjustment"] = (df.index.is_leap_year) & (df.index.dayofyear >= 59)
        df["hour_of_year"] = (
            1 + df.index.hour + (df.index.dayofyear - 1 - df.leap_adjustment) * 24
        )

        df = df.merge(temp_baseline, on="hour_of_year")

        # Calculate demand using the difference between actual indoor temperature
        # and the baseline temperature adjusted by tau
        hourly_cdd = (tau - (df.temperature_in - df.temperature_out)).apply(
            lambda x: np.maximum(x, 0)
        )
        # Aggregate to daily level
        demand = np.array(
            [
                cdd.sum() / 24
                for day, cdd in hourly_cdd.groupby(hourly_temp_out.index.date)
            ]
        )

        index = core_cooling_day_set.daily[core_cooling_day_set.daily].index
        return pd.Series(demand, index=index)

    def get_baseline_hourly_heating_demand(
        self, core_heating_day_set, temp_baseline, tau
    ):
        """NWMOD: Calculate baseline heating demand using a regional baseline.

        Returns
        -------
        baseline_hourly_demand : pd.Series
            Timeseries of daily demand using a regional baseline
        """
        self._protect_heating()

        # Get the outdoor temperature for this core day set
        hourly_temp_out = self.temperature_out[core_heating_day_set.hourly]
        if len(hourly_temp_out) == 0:
            return pd.Series()

        # Build a dataframe of outdoor temperature and merge it with the
        # baseline temperature timeseries
        df = pd.DataFrame()
        df["temperature_out"] = hourly_temp_out
        df.index = hourly_temp_out.index
        df["leap_adjustment"] = (df.index.is_leap_year) & (df.index.dayofyear >= 59)
        df["hour_of_year"] = (
            1 + df.index.hour + (df.index.dayofyear - 1 - df.leap_adjustment) * 24
        )

        df = df.merge(temp_baseline, on="hour_of_year")

        # Calculate demand using the difference between actual indoor temperature
        # and the baseline temperature adjusted by tau
        hourly_hdd = (df.temperature_in - df.temperature_out - tau).apply(
            lambda x: np.maximum(x, 0)
        )
        # Aggregate to daily level
        demand = np.array(
            [
                hdd.sum() / 24
                for day, hdd in hourly_hdd.groupby(hourly_temp_out.index.date)
            ]
        )

        index = core_heating_day_set.daily[core_heating_day_set.daily].index
        return pd.Series(demand, index=index)

    def calculate_epa_field_savings_metrics(
        self,
        core_cooling_day_set_method="year_end_to_end",
        core_heating_day_set_method="year_mid_to_mid",
        climate_zone_mapping=None,
    ):
        """Calculates metrics for connected thermostat savings as defined by
        the specification defined by the EPA Energy Star program and stakeholders.

        Parameters
        ----------
        core_cooling_day_set_method : {"entire_dataset", "year_end_to_end"}, default: "entire_dataset"
            Method by which to find core cooling day sets.

            - "entire_dataset": all core cooling days in dataset (days with >= 1
              hour of cooling runtime and no heating runtime.
            - "year_end_to_end": groups all core cooling days (days with >= 1 hour of total
              cooling and no heating) from January 1 to December 31 into
              independent core cooling day sets.
        core_heating_day_set_method : {"entire_dataset", "year_mid_to_mid"}, default: "entire_dataset"
            Method by which to find core heating day sets.

            - "entire_dataset": all core heating days in dataset (days with >= 1
              hour of heating runtime and no cooling runtime.
            - "year_mid_to_mid": groups all core heating days (days with >= 1 hour
              of total heating and no cooling) from July 1 to June 30 into
              independent core heating day sets.

        climate_zone_mapping : filename, default: None

            A mapping from climate zone to zipcode. If None is provided, uses
            default zipcode to climate zone mapping provided in tutorial.

            :download:`default mapping <./resources/Building America Climate Zone to Zipcode Database_Rev2_2016.09.08.csv>`

        Returns
        -------
        metrics : list
            list of dictionaries of output metrics; one per set of core heating
            or cooling days.
        """

        retval = retrieve_climate_zone(climate_zone_mapping, self.zipcode)
        climate_zone = retval.climate_zone
        baseline_regional_cooling_comfort_temperature = (
            retval.baseline_regional_cooling_comfort_temperature
        )
        baseline_regional_heating_comfort_temperature = (
            retval.baseline_regional_heating_comfort_temperature
        )

        metrics = []

        if self.has_cooling:
            for core_cooling_day_set in self.get_core_cooling_days(
                method=core_cooling_day_set_method
            ):

                outputs = self._calculate_cooling_epa_field_savings_metrics(
                    climate_zone,
                    core_cooling_day_set,
                    core_cooling_day_set_method,
                    baseline_regional_cooling_comfort_temperature,
                )
                metrics.append(outputs)

        if self.has_heating:
            for core_heating_day_set in self.get_core_heating_days(
                method=core_heating_day_set_method
            ):
                outputs = self._calculate_heating_epa_field_savings_metrics(
                    climate_zone,
                    core_heating_day_set,
                    core_heating_day_set_method,
                    baseline_regional_heating_comfort_temperature,
                )

                if self.has_auxiliary and self.has_emergency:
                    additional_outputs = (
                        self._calculate_aux_emerg_epa_field_savings_metrics(
                            core_heating_day_set
                        )
                    )
                    outputs.update(additional_outputs)

                metrics.append(outputs)
        return metrics

    def _calculate_cooling_epa_field_savings_metrics(
        self,
        climate_zone,
        core_cooling_day_set,
        core_cooling_day_set_method,
        baseline_regional_cooling_comfort_temperature,
    ):
        baseline10_comfort_temperature = self.get_core_cooling_day_baseline_setpoint(
            core_cooling_day_set
        )

        daily_runtime = self.cool_runtime_daily[core_cooling_day_set.daily]

        (
            demand,
            tau,
            alpha,
            mse,
            rmse,
            cvrmse,
            mape,
            mae,
            cov_x,
            nfev,
            mesg,
        ) = self.get_cooling_demand(core_cooling_day_set)

        total_runtime_core_cooling = daily_runtime.sum()
        n_days = core_cooling_day_set.daily.sum()
        n_hours = core_cooling_day_set.hourly.sum()

        if np.isnan(total_runtime_core_cooling):
            warnings.warn(
                "WARNING: Total Runtime Core Cooling Days is nan. "
                "This may mean that you have pandas 0.21.x installed "
                "(which is not supported)."
            )

        if n_days == 0:
            warnings.warn("WARNING: Number of valid cooling days is zero.")

        if n_hours == 0:
            warnings.warn("WARNING: Number of valid cooling hours is zero.")

        average_daily_cooling_runtime = np.divide(total_runtime_core_cooling, n_days)

        avg_daily_cooling_runtime = self.cool_runtime_daily[
            core_cooling_day_set.daily
        ].mean()
        avg_daily_heating_runtime = self.heat_runtime_daily[
            core_cooling_day_set.daily
        ].mean()
        avg_daily_auxiliary_runtime = self.auxiliary_runtime_daily[
            core_cooling_day_set.daily
        ].mean()
        avg_daily_emergency_runtime = self.emergency_runtime_daily[
            core_cooling_day_set.daily
        ].mean()

        baseline10_demand = self.get_baseline_cooling_demand(
            core_cooling_day_set,
            baseline10_comfort_temperature,
            tau,
        )

        baseline10_runtime = self.get_baseline_cooling_runtime(baseline10_demand, alpha)

        avoided_runtime_baseline10 = avoided(baseline10_runtime, daily_runtime)

        savings_baseline10 = percent_savings(
            avoided_runtime_baseline10, baseline10_runtime, self.thermostat_id
        )

        if baseline_regional_cooling_comfort_temperature is not None:

            baseline_regional_demand = self.get_baseline_cooling_demand(
                core_cooling_day_set, baseline_regional_cooling_comfort_temperature, tau
            )

            baseline_regional_runtime = self.get_baseline_cooling_runtime(
                baseline_regional_demand, alpha
            )

            avoided_runtime_baseline_regional = avoided(
                baseline_regional_runtime, daily_runtime
            )

            percent_savings_baseline_regional = percent_savings(
                avoided_runtime_baseline_regional,
                baseline_regional_runtime,
                self.thermostat_id,
            )

            avoided_daily_mean_core_day_runtime_baseline_regional = (
                avoided_runtime_baseline_regional.mean()
            )
            avoided_total_core_day_runtime_baseline_regional = (
                avoided_runtime_baseline_regional.sum()
            )
            baseline_daily_mean_core_day_runtime_baseline_regional = (
                baseline_regional_runtime.mean()
            )
            baseline_total_core_day_runtime_baseline_regional = (
                baseline_regional_runtime.sum()
            )
            _daily_mean_core_day_demand_baseline_baseline_regional = np.nanmean(
                baseline_regional_demand
            )

        else:

            baseline_regional_demand = None
            baseline_regional_runtime = None

            avoided_runtime_baseline_regional = None

            percent_savings_baseline_regional = None
            avoided_daily_mean_core_day_runtime_baseline_regional = None
            avoided_total_core_day_runtime_baseline_regional = None
            baseline_daily_mean_core_day_runtime_baseline_regional = None
            baseline_total_core_day_runtime_baseline_regional = None
            _daily_mean_core_day_demand_baseline_baseline_regional = None

        if self.hourly_temperature_baseline_cooling is not None:

            baseline_hourly_regional_demand = self.get_baseline_hourly_cooling_demand(
                core_cooling_day_set,
                self.hourly_temperature_baseline_cooling,
                tau,
            )

            baseline_hourly_regional_runtime = self.get_baseline_cooling_runtime(
                baseline_hourly_regional_demand,
                alpha,
            )

            avoided_runtime_baseline_hourly_regional = avoided(
                baseline_hourly_regional_runtime, daily_runtime
            )

            percent_savings_baseline_hourly_regional = percent_savings(
                avoided_runtime_baseline_hourly_regional,
                baseline_hourly_regional_runtime,
                self.thermostat_id,
            )

            avoided_daily_mean_core_day_runtime_baseline_hourly_regional = (
                avoided_runtime_baseline_hourly_regional.mean()
            )
            avoided_total_core_day_runtime_baseline_hourly_regional = (
                avoided_runtime_baseline_hourly_regional.sum()
            )
            baseline_daily_mean_core_day_runtime_baseline_hourly_regional = (
                baseline_hourly_regional_runtime.mean()
            )
            baseline_total_core_day_runtime_baseline_hourly_regional = (
                baseline_hourly_regional_runtime.sum()
            )
            _daily_mean_core_day_demand_baseline_baseline_hourly_regional = np.nanmean(
                baseline_hourly_regional_demand
            )

        else:

            baseline_hourly_regional_demand = None

            baseline_hourly_regional_runtime = None

            avoided_runtime_baseline_hourly_regional = None

            percent_savings_baseline_hourly_regional = None
            avoided_daily_mean_core_day_runtime_baseline_hourly_regional = None
            avoided_total_core_day_runtime_baseline_hourly_regional = None
            baseline_daily_mean_core_day_runtime_baseline_hourly_regional = None
            baseline_total_core_day_runtime_baseline_hourly_regional = None
            _daily_mean_core_day_demand_baseline_baseline_hourly_regional = None

        n_days_both, n_days_insufficient_data = self.get_ignored_days(
            core_cooling_day_set
        )
        n_core_cooling_days = self.get_core_day_set_n_days(core_cooling_day_set)
        n_days_in_inputfile_date_range = self.get_inputfile_date_range(
            core_cooling_day_set
        )

        core_cooling_days_mean_indoor_temperature = self.temperature_in[
            core_cooling_day_set.hourly
        ].mean()
        core_cooling_days_mean_outdoor_temperature = self.temperature_out[
            core_cooling_day_set.hourly
        ].mean()

        heat_gain_constant, heat_loss_constant = self.get_temperature_constants(
            core_cooling_day_set
        )
        hvac_constant = self.get_cooling_hvac_constant(core_cooling_day_set)
        (
            overall_temperature_variance,
            weekly_temperature_variance,
        ) = self.get_temperature_variance(core_cooling_day_set)

        (
            lm_intercept,
            lm_intercept_se,
            lm_main_slope,
            lm_main_slope_se,
            lm_secondary_slope,
            lm_secondary_slope_se,
            lm_cvrmse,
            lm_rsquared,
            excess_resistance_score_1hr,
            excess_resistance_score_2hr,
            excess_resistance_score_3hr,
        ) = self.fit_linear_cooling_model(core_cooling_day_set)

        outputs = {
            "sw_version": get_version(),
            "ct_identifier": self.thermostat_id,
            "heat_type": self.heat_type,
            "heat_stage": self.heat_stage,
            "cool_type": self.cool_type,
            "cool_stage": self.cool_stage,
            "heating_or_cooling": core_cooling_day_set.name,
            "zipcode": self.zipcode,
            "station": self.station,
            "climate_zone": climate_zone,
            "start_date": pd.Timestamp(core_cooling_day_set.start_date)
            .to_pydatetime()
            .isoformat(),
            "end_date": pd.Timestamp(core_cooling_day_set.end_date)
            .to_pydatetime()
            .isoformat(),
            "n_days_in_inputfile_date_range": n_days_in_inputfile_date_range,
            "n_days_both_heating_and_cooling": n_days_both,
            "n_days_insufficient_data": n_days_insufficient_data,
            "n_core_cooling_days": n_core_cooling_days,
            "baseline_percentile_core_cooling_comfort_temperature": baseline10_comfort_temperature,
            "regional_average_baseline_cooling_comfort_temperature": baseline_regional_cooling_comfort_temperature,
            "percent_savings_baseline_percentile": savings_baseline10,
            "avoided_daily_mean_core_day_runtime_baseline_percentile": avoided_runtime_baseline10.mean(),
            "avoided_total_core_day_runtime_baseline_percentile": avoided_runtime_baseline10.sum(),
            "baseline_daily_mean_core_day_runtime_baseline_percentile": baseline10_runtime.mean(),
            "baseline_total_core_day_runtime_baseline_percentile": baseline10_runtime.sum(),
            "_daily_mean_core_day_demand_baseline_baseline_percentile": np.nanmean(
                baseline10_demand
            ),
            "percent_savings_baseline_regional": percent_savings_baseline_regional,
            "avoided_daily_mean_core_day_runtime_baseline_regional": avoided_daily_mean_core_day_runtime_baseline_regional,
            "avoided_total_core_day_runtime_baseline_regional": avoided_total_core_day_runtime_baseline_regional,
            "baseline_daily_mean_core_day_runtime_baseline_regional": baseline_daily_mean_core_day_runtime_baseline_regional,
            "baseline_total_core_day_runtime_baseline_regional": baseline_total_core_day_runtime_baseline_regional,
            "_daily_mean_core_day_demand_baseline_baseline_regional": _daily_mean_core_day_demand_baseline_baseline_regional,
            "percent_savings_baseline_hourly_regional": percent_savings_baseline_hourly_regional,
            "avoided_daily_mean_core_day_runtime_baseline_hourly_regional": avoided_daily_mean_core_day_runtime_baseline_hourly_regional,
            "avoided_total_core_day_runtime_baseline_hourly_regional": avoided_total_core_day_runtime_baseline_hourly_regional,
            "baseline_daily_mean_core_day_runtime_baseline_hourly_regional": baseline_daily_mean_core_day_runtime_baseline_hourly_regional,
            "baseline_total_core_day_runtime_baseline_hourly_regional": baseline_total_core_day_runtime_baseline_hourly_regional,
            "_daily_mean_core_day_demand_baseline_baseline_hourly_regional": _daily_mean_core_day_demand_baseline_baseline_hourly_regional,
            "mean_demand": np.nanmean(demand),
            "tau": tau,
            "alpha": alpha,
            "mean_sq_err": mse,
            "root_mean_sq_err": rmse,
            "cv_root_mean_sq_err": cvrmse,
            "mean_abs_pct_err": mape,
            "mean_abs_err": mae,
            "cov_x": cov_x,
            "nfev": nfev,
            "mesg": mesg,
            "total_core_cooling_runtime": total_runtime_core_cooling,
            "daily_mean_core_cooling_runtime": average_daily_cooling_runtime,
            "core_cooling_days_mean_indoor_temperature": core_cooling_days_mean_indoor_temperature,
            "core_cooling_days_mean_outdoor_temperature": core_cooling_days_mean_outdoor_temperature,
            "core_mean_indoor_temperature": core_cooling_days_mean_indoor_temperature,
            "core_mean_outdoor_temperature": core_cooling_days_mean_outdoor_temperature,
            "heat_gain_constant": heat_gain_constant,
            "heat_loss_constant": heat_loss_constant,
            "hvac_constant": hvac_constant,
            "overall_temperature_variance": overall_temperature_variance,
            "weekly_temperature_variance": weekly_temperature_variance,
            "avg_daily_cooling_runtime": avg_daily_cooling_runtime,
            "avg_daily_heating_runtime": avg_daily_heating_runtime,
            "avg_daily_auxiliary_runtime": avg_daily_auxiliary_runtime,
            "avg_daily_emergency_runtime": avg_daily_emergency_runtime,
            "lm_intercept": lm_intercept,
            "lm_intercept_se": lm_intercept_se,
            "lm_main_slope": lm_main_slope,
            "lm_main_slope_se": lm_main_slope_se,
            "lm_secondary_slope": lm_secondary_slope,
            "lm_secondary_slope_se": lm_secondary_slope_se,
            "lm_cvrmse": lm_cvrmse,
            "lm_rsquared": lm_rsquared,
            "excess_resistance_score_1hr": excess_resistance_score_1hr,
            "excess_resistance_score_2hr": excess_resistance_score_2hr,
            "excess_resistance_score_3hr": excess_resistance_score_3hr,
        }
        return outputs

    def _calculate_heating_epa_field_savings_metrics(
        self,
        climate_zone,
        core_heating_day_set,
        core_heating_day_set_method,
        baseline_regional_heating_comfort_temperature,
    ):

        baseline90_comfort_temperature = self.get_core_heating_day_baseline_setpoint(
            core_heating_day_set
        )

        # deltaT
        daily_runtime = self.heat_runtime_daily[core_heating_day_set.daily]

        (
            demand,
            tau,
            alpha,
            mse,
            rmse,
            cvrmse,
            mape,
            mae,
            cov_x,
            nfev,
            mesg,
        ) = self.get_heating_demand(core_heating_day_set)

        self.heating_demand = demand.copy()
        self.tau = tau

        total_runtime_core_heating = daily_runtime.sum()
        n_days = core_heating_day_set.daily.sum()
        n_hours = core_heating_day_set.hourly.sum()

        if np.isnan(total_runtime_core_heating):
            warnings.warn(
                "WARNING: Total Runtime Core Heating is nan. "
                "This may mean that you have pandas 0.21.x installed "
                "(which is not supported)."
            )

        if n_days == 0:
            warnings.warn("WARNING: Number of valid heating days is zero.")

        if n_hours == 0:
            warnings.warn("WARNING: Number of valid cooling hours is zero.")

        average_daily_heating_runtime = np.divide(total_runtime_core_heating, n_days)

        avg_daily_cooling_runtime = self.cool_runtime_daily[
            core_heating_day_set.daily
        ].mean()
        avg_daily_heating_runtime = self.heat_runtime_daily[
            core_heating_day_set.daily
        ].mean()
        avg_daily_auxiliary_runtime = self.auxiliary_runtime_daily[
            core_heating_day_set.daily
        ].mean()
        avg_daily_emergency_runtime = self.emergency_runtime_daily[
            core_heating_day_set.daily
        ].mean()

        baseline90_demand = self.get_baseline_heating_demand(
            core_heating_day_set,
            baseline90_comfort_temperature,
            tau,
        )

        baseline90_runtime = self.get_baseline_heating_runtime(
            baseline90_demand,
            alpha,
        )

        avoided_runtime_baseline90 = avoided(baseline90_runtime, daily_runtime)

        savings_baseline90 = percent_savings(
            avoided_runtime_baseline90, baseline90_runtime, self.thermostat_id
        )

        if baseline_regional_heating_comfort_temperature is not None:

            baseline_regional_demand = self.get_baseline_heating_demand(
                core_heating_day_set,
                baseline_regional_heating_comfort_temperature,
                tau,
            )

            baseline_regional_runtime = self.get_baseline_heating_runtime(
                baseline_regional_demand,
                alpha,
            )

            avoided_runtime_baseline_regional = avoided(
                baseline_regional_runtime, daily_runtime
            )

            percent_savings_baseline_regional = percent_savings(
                avoided_runtime_baseline_regional,
                baseline_regional_runtime,
                self.thermostat_id,
            )

            avoided_daily_mean_core_day_runtime_baseline_regional = (
                avoided_runtime_baseline_regional.mean()
            )
            avoided_total_core_day_runtime_baseline_regional = (
                avoided_runtime_baseline_regional.sum()
            )
            baseline_daily_mean_core_day_runtime_baseline_regional = (
                baseline_regional_runtime.mean()
            )
            baseline_total_core_day_runtime_baseline_regional = (
                baseline_regional_runtime.sum()
            )
            _daily_mean_core_day_demand_baseline_baseline_regional = np.nanmean(
                baseline_regional_demand
            )

        else:

            baseline_regional_demand = None

            baseline_regional_runtime = None

            avoided_runtime_baseline_regional = None

            percent_savings_baseline_regional = None
            avoided_daily_mean_core_day_runtime_baseline_regional = None
            avoided_total_core_day_runtime_baseline_regional = None
            baseline_daily_mean_core_day_runtime_baseline_regional = None
            baseline_total_core_day_runtime_baseline_regional = None
            _daily_mean_core_day_demand_baseline_baseline_regional = None

        if self.hourly_temperature_baseline_heating is not None:

            baseline_hourly_regional_demand = self.get_baseline_hourly_heating_demand(
                core_heating_day_set,
                self.hourly_temperature_baseline_heating,
                tau,
            )

            baseline_hourly_regional_runtime = self.get_baseline_heating_runtime(
                baseline_hourly_regional_demand,
                alpha,
            )

            avoided_runtime_baseline_hourly_regional = avoided(
                baseline_hourly_regional_runtime, daily_runtime
            )

            percent_savings_baseline_hourly_regional = percent_savings(
                avoided_runtime_baseline_hourly_regional,
                baseline_hourly_regional_runtime,
                self.thermostat_id,
            )

            avoided_daily_mean_core_day_runtime_baseline_hourly_regional = (
                avoided_runtime_baseline_hourly_regional.mean()
            )
            avoided_total_core_day_runtime_baseline_hourly_regional = (
                avoided_runtime_baseline_hourly_regional.sum()
            )
            baseline_daily_mean_core_day_runtime_baseline_hourly_regional = (
                baseline_hourly_regional_runtime.mean()
            )
            baseline_total_core_day_runtime_baseline_hourly_regional = (
                baseline_hourly_regional_runtime.sum()
            )
            _daily_mean_core_day_demand_baseline_baseline_hourly_regional = np.nanmean(
                baseline_hourly_regional_demand
            )

        else:

            baseline_hourly_regional_demand = None

            baseline_hourly_regional_runtime = None

            avoided_runtime_baseline_hourly_regional = None

            percent_savings_baseline_hourly_regional = None
            avoided_daily_mean_core_day_runtime_baseline_hourly_regional = None
            avoided_total_core_day_runtime_baseline_hourly_regional = None
            baseline_daily_mean_core_day_runtime_baseline_hourly_regional = None
            baseline_total_core_day_runtime_baseline_hourly_regional = None
            _daily_mean_core_day_demand_baseline_baseline_hourly_regional = None

        n_days_both, n_days_insufficient_data = self.get_ignored_days(
            core_heating_day_set
        )
        n_core_heating_days = self.get_core_day_set_n_days(core_heating_day_set)
        n_days_in_inputfile_date_range = self.get_inputfile_date_range(
            core_heating_day_set
        )

        core_heating_days_mean_indoor_temperature = self.temperature_in[
            core_heating_day_set.hourly
        ].mean()
        core_heating_days_mean_outdoor_temperature = self.temperature_out[
            core_heating_day_set.hourly
        ].mean()

        heat_gain_constant, heat_loss_constant = self.get_temperature_constants(
            core_heating_day_set
        )
        hvac_constant = self.get_heating_hvac_constant(core_heating_day_set)
        (
            overall_temperature_variance,
            weekly_temperature_variance,
        ) = self.get_temperature_variance(core_heating_day_set)

        (
            lm_intercept,
            lm_intercept_se,
            lm_main_slope,
            lm_main_slope_se,
            lm_secondary_slope,
            lm_secondary_slope_se,
            lm_cvrmse,
            lm_rsquared,
            excess_resistance_score_1hr,
            excess_resistance_score_2hr,
            excess_resistance_score_3hr,
        ) = self.fit_linear_heating_model(core_heating_day_set)

        outputs = {
            "sw_version": get_version(),
            "ct_identifier": self.thermostat_id,
            "heat_type": self.heat_type,
            "heat_stage": self.heat_stage,
            "cool_type": self.cool_type,
            "cool_stage": self.cool_stage,
            "heating_or_cooling": core_heating_day_set.name,
            "zipcode": self.zipcode,
            "station": self.station,
            "climate_zone": climate_zone,
            "start_date": pd.Timestamp(core_heating_day_set.start_date)
            .to_pydatetime()
            .isoformat(),
            "end_date": pd.Timestamp(core_heating_day_set.end_date)
            .to_pydatetime()
            .isoformat(),
            "n_days_in_inputfile_date_range": n_days_in_inputfile_date_range,
            "n_days_both_heating_and_cooling": n_days_both,
            "n_days_insufficient_data": n_days_insufficient_data,
            "n_core_heating_days": n_core_heating_days,
            "baseline_percentile_core_heating_comfort_temperature": baseline90_comfort_temperature,
            "regional_average_baseline_heating_comfort_temperature": baseline_regional_heating_comfort_temperature,
            "percent_savings_baseline_percentile": savings_baseline90,
            "avoided_daily_mean_core_day_runtime_baseline_percentile": avoided_runtime_baseline90.mean(),
            "avoided_total_core_day_runtime_baseline_percentile": avoided_runtime_baseline90.sum(),
            "baseline_daily_mean_core_day_runtime_baseline_percentile": baseline90_runtime.mean(),
            "baseline_total_core_day_runtime_baseline_percentile": baseline90_runtime.sum(),
            "_daily_mean_core_day_demand_baseline_baseline_percentile": np.nanmean(
                baseline90_demand
            ),
            "percent_savings_baseline_regional": percent_savings_baseline_regional,
            "avoided_daily_mean_core_day_runtime_baseline_regional": avoided_daily_mean_core_day_runtime_baseline_regional,
            "avoided_total_core_day_runtime_baseline_regional": avoided_total_core_day_runtime_baseline_regional,
            "baseline_daily_mean_core_day_runtime_baseline_regional": baseline_daily_mean_core_day_runtime_baseline_regional,
            "baseline_total_core_day_runtime_baseline_regional": baseline_total_core_day_runtime_baseline_regional,
            "_daily_mean_core_day_demand_baseline_baseline_regional": _daily_mean_core_day_demand_baseline_baseline_regional,
            "percent_savings_baseline_hourly_regional": percent_savings_baseline_hourly_regional,
            "avoided_daily_mean_core_day_runtime_baseline_hourly_regional": avoided_daily_mean_core_day_runtime_baseline_hourly_regional,
            "avoided_total_core_day_runtime_baseline_hourly_regional": avoided_total_core_day_runtime_baseline_hourly_regional,
            "baseline_daily_mean_core_day_runtime_baseline_hourly_regional": baseline_daily_mean_core_day_runtime_baseline_hourly_regional,
            "baseline_total_core_day_runtime_baseline_hourly_regional": baseline_total_core_day_runtime_baseline_hourly_regional,
            "_daily_mean_core_day_demand_baseline_baseline_hourly_regional": _daily_mean_core_day_demand_baseline_baseline_hourly_regional,
            "mean_demand": np.nanmean(demand),
            "tau": tau,
            "alpha": alpha,
            "mean_sq_err": mse,
            "root_mean_sq_err": rmse,
            "cv_root_mean_sq_err": cvrmse,
            "mean_abs_pct_err": mape,
            "mean_abs_err": mae,
            "cov_x": cov_x,
            "nfev": nfev,
            "mesg": mesg,
            "total_core_heating_runtime": total_runtime_core_heating,
            "daily_mean_core_heating_runtime": average_daily_heating_runtime,
            "core_heating_days_mean_indoor_temperature": core_heating_days_mean_indoor_temperature,
            "core_heating_days_mean_outdoor_temperature": core_heating_days_mean_outdoor_temperature,
            "core_mean_indoor_temperature": core_heating_days_mean_indoor_temperature,
            "core_mean_outdoor_temperature": core_heating_days_mean_outdoor_temperature,
            "heat_gain_constant": heat_gain_constant,
            "heat_loss_constant": heat_loss_constant,
            "hvac_constant": hvac_constant,
            "overall_temperature_variance": overall_temperature_variance,
            "weekly_temperature_variance": weekly_temperature_variance,
            "avg_daily_cooling_runtime": avg_daily_cooling_runtime,
            "avg_daily_heating_runtime": avg_daily_heating_runtime,
            "avg_daily_auxiliary_runtime": avg_daily_auxiliary_runtime,
            "avg_daily_emergency_runtime": avg_daily_emergency_runtime,
            "lm_intercept": lm_intercept,
            "lm_intercept_se": lm_intercept_se,
            "lm_main_slope": lm_main_slope,
            "lm_main_slope_se": lm_main_slope_se,
            "lm_secondary_slope": lm_secondary_slope,
            "lm_secondary_slope_se": lm_secondary_slope_se,
            "lm_cvrmse": lm_cvrmse,
            "lm_rsquared": lm_rsquared,
            "excess_resistance_score_1hr": excess_resistance_score_1hr,
            "excess_resistance_score_2hr": excess_resistance_score_2hr,
            "excess_resistance_score_3hr": excess_resistance_score_3hr,
        }

        return outputs

    def _rhu_outputs(self, rhu_type, rhu_bins, rhu_usage_bins, duty_cycle):
        """Helper function for formatting the RHU scores.
            rhu_type : str
                String representation of the RHU type (rhu1, rhu2)
            rhu_bins : Pandas series
                Data for the RHU calculation from get_resistance_heat_utilization_bins
            rhu_usage_bins :  list of tuples
                List of the lower and upper bounds for the given RHU bin to fill with None if rhu_bins is None
            duty_cycle : str
                The duty cycle (e.g.: None, 'aux_duty_cycle', 'emg_duty_cycle', 'compressor_duty_cycle')

        Returns
        -------
        local_outputs : dict
            Dictionary of the columns and RHU data for output
        """
        local_outputs = {}
        if rhu_bins is not None:
            for item in rhu_bins.itertuples():
                column = self._format_rhu(
                    rhu_type=rhu_type,
                    low=item.Index.left,
                    high=item.Index.right,
                    duty_cycle=duty_cycle,
                )
                if duty_cycle is None:
                    local_outputs[column] = item.rhu
                else:
                    local_outputs[column] = getattr(item, duty_cycle)
        else:
            for (low, high) in rhu_usage_bins:
                column = self._format_rhu(rhu_type, low, high, duty_cycle)

                local_outputs[column] = None
        return local_outputs

    def _calculate_aux_emerg_epa_field_savings_metrics(self, core_heating_day_set):
        additional_outputs = {
            "total_auxiliary_heating_core_day_runtime": self.total_auxiliary_heating_runtime(
                core_heating_day_set
            ),
            "total_emergency_heating_core_day_runtime": self.total_emergency_heating_runtime(
                core_heating_day_set
            ),
        }

        # Add RHU Calculations
        for rhu_type in ("rhu1", "rhu2"):
            if rhu_type == "rhu2":
                min_runtime_minutes = VAR_MIN_RHU_RUNTIME
            else:
                min_runtime_minutes = None

            rhu_runtime = self.get_resistance_heat_utilization_runtime(
                core_heating_day_set
            )

            rhu = self.get_resistance_heat_utilization_bins(
                rhu_runtime,
                RESISTANCE_HEAT_USE_BIN,
                core_heating_day_set,
                min_runtime_minutes,
            )

            rhu_wide = self.get_resistance_heat_utilization_bins(
                rhu_runtime,
                RESISTANCE_HEAT_USE_WIDE_BIN,
                core_heating_day_set,
                min_runtime_minutes,
            )

            # We no longer track different duty cycles (aux, emg, compressor, etc.)
            duty_cycle = None

            additional_outputs.update(
                self.get_rh_metrics_daily(
                    bins=RESISTANCE_HEAT_USE_BIN, core_day_set=core_heating_day_set
                )
            )
            additional_outputs.update(
                self.get_rh_metrics_hourly(
                    bins=RESISTANCE_HEAT_USE_BIN, core_day_set=core_heating_day_set
                )
            )
            additional_outputs.update(
                self._rhu_outputs(
                    rhu_type=rhu_type,
                    rhu_bins=rhu,
                    rhu_usage_bins=RESISTANCE_HEAT_USE_BIN_PAIRS,
                    duty_cycle=duty_cycle,
                )
            )

            additional_outputs.update(
                self._rhu_outputs(
                    rhu_type=rhu_type,
                    rhu_bins=rhu_wide,
                    rhu_usage_bins=RESISTANCE_HEAT_USE_WIDE_BIN_PAIRS,
                    duty_cycle=duty_cycle,
                )
            )

        return additional_outputs
