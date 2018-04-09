# -*- coding: utf-8 -*-
"""
Authors: Hung-Hsin Chen <chenhh@par.cse.nsysu.edu.tw>

https://github.com/ipython/ipyparallel/blob/master/examples/customresults.py
https://github.com/ipython/ipyparallel/blob/master/ipyparallel/client/asyncresult.py
"""

import datetime as dt
import glob
import json
import logging
import os
import platform
import sys
from time import (time, sleep)

import ipyparallel as ipp
import numpy as np
import scipy.stats as spstats
import xarray as xr

import portfolio_programming as pp
from portfolio_programming.sampling.moment_matching import (
    heuristic_moment_matching as HeMM)


def hemm_generating_scenarios_xarr(scenario_set_idx,
                                   scenario_start_date,
                                   scenario_end_date,
                                   n_symbol,
                                   rolling_window_size,
                                   n_scenario,
                                   retry_cnt=5,
                                   print_interval=10):
    """
    generating scenarios xarray using Heuristic moment matching

    Parameters:
    ------------------
    scenario_set_idx: positive integer
    scenario_start_date, scenario_end_date : datetime.date
    n_stock: positive integer, number of stocks in the candidate symbols
    rolling_window_size: positive integer, number of historical periods
    n_scenario: integer, number of scenarios to generating
    retry_cnt: positive integer, maximum retry of scenarios
    print_interval: positive integer

    Returns:
    ------------------
    scenario_xarr : xarray.DataArray, dim:(trans_date, symbol, scenario)
    """

    t0 = time()

    # scenario dir
    if not os.path.exists(pp.SCENARIO_SET_DIR):
        os.makedirs(pp.SCENARIO_SET_DIR)

    scenario_file = pp.SCENARIO_NAME_FORMAT.format(
        sdx=scenario_set_idx,
        scenario_start_date=scenario_start_date.strftime("%Y%m%d"),
        scenario_end_date=scenario_end_date.strftime("%Y%m%d"),
        n_symbol=n_symbol,
        rolling_window_size=rolling_window_size,
        n_scenario=n_scenario
    )

    scenario_path = os.path.join(pp.SCENARIO_SET_DIR, scenario_file)
    if os.path.exists(scenario_path):
        return "{} exists.".format(scenario_file)

    parameters = "{}_{} scenarios-set-idx{}_{}_{}_Mc{}_h{}_s{}".format(
        platform.node(),
        os.getpid(),
        scenario_set_idx,
        scenario_start_date.strftime("%Y%m%d"),
        scenario_end_date.strftime("%Y%m%d"),
        n_symbol,
        rolling_window_size,
        n_scenario,
    )

    # read roi data
    # shape: (n_period, n_stock, 6 attributes)
    risky_asset_xarr = xr.open_dataarray(
        pp.TAIEX_2005_LARGESTED_MARKET_CAP_DATA_NC)

    # symbols
    with open(pp.TAIEX_2005_LARGEST4ED_MARKET_CAP_SYMBOL_JSON) as fin:
        candidate_symbols = json.load(fin)[:n_symbol]

    # all trans_date, pandas.core.indexes.datetimes.DatetimeIndex
    trans_dates = risky_asset_xarr.get_index('trans_date')

    # experiment trans_dates
    sc_start_idx = trans_dates.get_loc(scenario_start_date)
    sc_end_idx = trans_dates.get_loc(scenario_end_date)
    sc_trans_dates = trans_dates[sc_start_idx: sc_end_idx + 1]
    n_sc_period = len(sc_trans_dates)

    # estimating moments and correlation matrix
    est_moments = xr.DataArray(np.zeros((n_symbol, 4)),
                               dims=('symbol', 'moment'),
                               coords=(candidate_symbols,
                                       ['mean', 'std', 'skew', 'ex-kurt']))

    # output scenario xarray, shape: (n_sc_period, n_stock, n_scenario)
    scenario_xarr = xr.DataArray(
        np.zeros((n_sc_period, n_symbol, n_scenario)),
        dims=('trans_date', 'symbol', 'scenario'),
        coords=(sc_trans_dates, candidate_symbols, range(n_scenario)),
    )

    for tdx, sc_date in enumerate(sc_trans_dates):
        t1 = time()

        # rolling historical window indices, containing today
        est_start_idx = sc_start_idx + tdx - rolling_window_size + 1
        est_end_idx = sc_start_idx + tdx + 1
        hist_interval = trans_dates[est_start_idx:est_end_idx]

        assert len(hist_interval) == rolling_window_size
        assert hist_interval[-1] == sc_date

        # hist_data, shape: (win_length, n_stock)
        hist_data = risky_asset_xarr.loc[hist_interval,
                                         candidate_symbols,
                                         'simple_roi']

        # unbiased moments and corrs estimators
        est_moments.loc[:, 'mean'] = hist_data.mean(axis=0)
        est_moments.loc[:, 'std'] = hist_data.std(axis=0, ddof=1)
        est_moments.loc[:, 'skew'] = spstats.skew(hist_data, axis=0, bias=False)
        est_moments.loc[:, 'ex-kurt'] = spstats.kurtosis(hist_data, axis=0,
                                                         bias=False)
        # est_corrs = (hist_data.T).corr("pearson")
        est_corrs = np.corrcoef(hist_data.T)

        # generating unbiased scenario
        for error_count in range(retry_cnt):
            try:
                for error_exponent in range(-3, 0):
                    try:
                        # default moment and corr errors (1e-3, 1e-3)
                        # df shape: (n_stock, n_scenario)
                        max_moment_err = 10 ** error_exponent
                        max_corr_err = 10 ** error_exponent
                        scenario_df = HeMM(est_moments.values,
                                           est_corrs,
                                           n_scenario,
                                           False,
                                           max_moment_err,
                                           max_corr_err)
                    except ValueError as _:
                        logging.warning(
                            "{} relaxing max err: {}_max_mom_err:{}, "
                            "max_corr_err{}".format(
                                parameters, sc_date,
                                max_moment_err, max_corr_err))
                    else:
                        # generating scenarios success
                        break

            except Exception as e:
                # catch any other exception
                if error_count == retry_cnt - 1:
                    raise Exception(e)
            else:
                # generating scenarios success
                break

        # store scenarios, scenario_df shape: (n_stock, n_scenario)
        scenario_xarr.loc[sc_date, :, :] = scenario_df

        # clear est data
        if tdx % print_interval == 0:
            logging.info("{} [{}/{}] {} OK, {:.4f} secs".format(
                sc_date.strftime("%Y%m%d"),
                tdx + 1,
                n_sc_period,
                parameters,
                time() - t1))

    # write scenario
    scenario_xarr.to_netcdf(scenario_path)

    msg = ("generating scenarios {} OK, {:.3f} secs".format(
        parameters, time() - t0))
    logging.info(msg)
    return msg


def _hemm_all_scenario_names():
    """
    "TAIEX_2005_largested_market_cap_" \
       "scenario-set-idx{sdx}_" \
       "{scenario_start_date}_" \
       "{scenario_end_date}_" \
       "Mc{n_symbol}_" \
       "h{rolling_window_size}_s{n_scenario}.nc"
    """
    set_indices = (1, 2, 3)
    s_date = pp.SCENARIO_START_DATE
    e_date = pp.SCENARIO_END_DATE
    n_symbols = range(5, 55, 5)
    window_sizes = range(60, 240 + 10, 10)
    n_scenarios = [200, ]

    # dict comprehension
    # key: file_name, value: parameters
    return {
        pp.SYMBOL_SCENARIO_NAME_FORMAT.format(
            sdx=sdx,
            scenario_start_date=s_date.strftime("%Y%m%d"),
            scenario_end_date=e_date.strftime("%Y%m%d"),
            n_symbol=m,
            rolling_window_size=h,
            n_scenario=s
        ): (sdx, s_date, e_date, m, h, s)
        for sdx in set_indices
        for m in n_symbols
        for h in window_sizes
        for s in n_scenarios
    }


def hemm_checking_existed_scenario_names(scenario_set_dir=None):
    """
    return unfinished experiment parameters.
    """
    if scenario_set_dir is None:
        scenario_set_dir = pp.SCENARIO_SET_DIR
    all_names = _hemm_all_scenario_names()

    os.chdir(scenario_set_dir)
    existed_names = glob.glob("*.nc")
    for name in existed_names:
        all_names.pop(name, None)

    # unfinished params
    return all_names


def hemm_dispatch_scenario_names(scenario_set_dir=pp.SCENARIO_SET_DIR):
    unfinished_names = hemm_checking_existed_scenario_names(scenario_set_dir)
    print("number of unfinished scenario: {}".format(len(unfinished_names)))
    params = unfinished_names.values()

    # task interface
    rc = ipp.Client(profile='ssh')
    dv = rc[:]
    dv.use_dill()
    dv.scatter('engine_id', rc.ids, flatten=True)
    print("Engine IDs: ", dv['engine_id'])
    n_engine = len(rc.ids)

    with dv.sync_imports():
        import sys
        import platform
        import os
        import portfolio_programming.simulation.hemm_gen_scenarios

    def name_pid():
        return "node:{}, pid:{}".format(
            platform.node(), os.getpid())

    infos = dv.apply_sync(name_pid)
    for info in infos:
        print(info)

    lbv = rc.load_balanced_view()
    print("start map unfinished parameters to load balance view.")
    try:
        #  ipyparallel.client.asyncresult.AsyncMapResult
        ar = lbv.map_async(
            lambda
                x: portfolio_programming.simulation.gen_scenarios.hemm_generating_scenarios_xarr(
                *x),
            params)

        while not ar.ready():
            print("{} n_engine:{} gen_scenarios task: {}/{} {:10.1f} "
                  "secs".format(
                str(dt.datetime.now()), n_engine, ar.progress, len(ar),
                ar.elapsed))
            sys.stdout.flush()
            sleep(10)

            # type(ar.stdout) == list, and the length is equal to the number of
            # task.
            stdouts = ar.stdout
            if not any(stdouts):
                continue

            for task_idx, outs in enumerate(stdouts):
                print("{}: {}".format(task_idx, outs.split('\n')[-1]))
            sys.stdout.flush()

    except Exception as e:
        print(e)
        ar.abort()
        sys.exit(1)

    print(ar.get())
    print("speed up:{:.2%}".format(ar.serial_time / ar.wall_time))


def merge_scenario(s_date1=dt.date(2005, 1, 3), e_date1=dt.date(2014, 12, 31),
                   s_date2=dt.date(2015, 1, 5), e_date2=dt.date(2017, 12, 29)):
    """
    SCENARIO_NAME_FORMAT = "TAIEX_2005_largested_market_cap_" \
                       "scenario-set-idx{sdx}_" \
                       "{scenario_start_date}_" \
                       "{scenario_end_date}_" \
                       "Mc{n_symbol}_" \
                       "h{rolling_window_size}_s{n_scenario}.nc"
    """
    set_indices = (1, 2, 3)
    # set_indices = (2,)
    n_symbols = range(5, 50 + 5, 5)
    window_sizes = range(60, 240 + 10, 10)
    n_scenarios = [200, ]

    merge_count = 0
    unfinished_params = []
    # dict comprehension
    # key: file_name, value: parameters
    for sdx in set_indices:
        for m in n_symbols:
            for h in window_sizes:
                for s in n_scenarios:
                    nc1 = pp.SCENARIO_NAME_FORMAT.format(
                        sdx=sdx,
                        scenario_start_date=s_date1.strftime("%Y%m%d"),
                        scenario_end_date=e_date1.strftime("%Y%m%d"),
                        n_symbol=m,
                        rolling_window_size=h,
                        n_scenario=s
                    )

                    nc2 = pp.SCENARIO_NAME_FORMAT.format(
                        sdx=sdx,
                        scenario_start_date=s_date2.strftime("%Y%m%d"),
                        scenario_end_date=e_date2.strftime("%Y%m%d"),
                        n_symbol=m,
                        rolling_window_size=h,
                        n_scenario=s
                    )

                    concat_nc = pp.SCENARIO_NAME_FORMAT.format(
                        sdx=sdx,
                        scenario_start_date=s_date1.strftime("%Y%m%d"),
                        scenario_end_date=e_date2.strftime("%Y%m%d"),
                        n_symbol=m,
                        rolling_window_size=h,
                        n_scenario=s
                    )

                    scenario_path = os.path.join(pp.SCENARIO_SET_DIR,
                                                 concat_nc)
                    nc1_path = os.path.join(pp.SCENARIO_SET_DIR,
                                            nc1)
                    nc2_path = os.path.join(pp.SCENARIO_SET_DIR, nc2)

                    print('merged scenario: {}'.format(merge_count))
                    if os.path.exists(scenario_path):
                        logging.info("{} exists.".format(concat_nc))
                        merge_count += 1
                        continue

                    if os.path.exists(nc1_path):
                        xarr1 = xr.open_dataarray(open(nc1_path, 'rb'))
                    else:
                        logging.info('{} does not exist.'.format(nc1))
                        unfinished_params.append(nc1_path)
                        continue

                    if os.path.exists(nc2_path):
                        xarr2 = xr.open_dataarray(open(nc2_path, 'rb'))
                    else:
                        logging.info('{} does not exist.'.format(nc2))
                        unfinished_params.append(nc2_path)
                        continue

                    concat_xarr = xr.concat([xarr1, xarr2],
                                            dim='trans_date')
                    concat_xarr.to_netcdf(scenario_path)
                    logging.info('concat scenario {} and {} to {}'.format(
                        nc1, nc2, concat_nc
                    ))
                    merge_count += 1

    logging.info("unfinished parameters")
    for param in unfinished_params:
        logging.info(param)


if __name__ == '__main__':
    # using stdout instead of stderr
    logging.basicConfig(
        stream=sys.stdout,
        format='%(filename)15s %(levelname)10s %(asctime)s\n'
               '%(message)s',
        datefmt='%Y%m%d-%H:%M:%S',
        level=logging.INFO)

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", '--parallel',
                        default=False,
                        action='store_true',
                        help="parallel mode or not")

    parser.add_argument('--merge',
                        default=False,
                        action='store_true',
                        help="merged scenario")

    parser.add_argument("-n", "--n_candidate_symbol", type=int,
                        choices=range(1, 51),
                        help="number of candidate symbol")

    parser.add_argument("-w", "--rolling_window_size", type=int,
                        choices=range(50, 250),
                        help="rolling window size for estimating statistics.")

    parser.add_argument("-s", '--n_scenario', type=int,
                        choices=range(200, 1000, 10),
                        default=200,
                        help="number of generated scenario.")

    parser.add_argument("--scenario-set-idx", type=int,
                        choices=range(1, 4),
                        default=1,
                        help="pre-generated scenario set index.")

    args = parser.parse_args()
    if args.parallel:
        print("generating scenario in parallel mode")
        hemm_dispatch_scenario_names()
    elif args.merge:
        merge_scenario()
    else:
        print("generating scenario in single mode")
        hemm_generating_scenarios_xarr(args.scenario_set_idx,
                                       pp.SCENARIO_START_DATE,
                                       pp.SCENARIO_END_DATE,
                                       args.n_candidate_symbol,
                                       args.rolling_window_size,
                                       args.n_scenario
                                       )