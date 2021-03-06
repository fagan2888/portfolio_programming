# -*- coding: utf-8 -*-
"""
Author: Hung-Hsin Chen <chen1116@gmail.com>
"""

import csv
import datetime as dt
import logging
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

import portfolio_programming as pp
from portfolio_programming.simulation.wp_bah import BAHPortfolio


def run_bah(exp_name, group_name, exp_start_date, exp_end_date):
    group_symbols = pp.GROUP_SYMBOLS
    if group_name not in group_symbols.keys():
        raise ValueError('Unknown group name:{}'.format(group_name))
    symbols = group_symbols[group_name]
    n_symbol = len(symbols)

    market = group_name[:2]
    if market == "TW":
        roi_xarr = xr.open_dataarray(pp.TAIEX_2005_MKT_CAP_NC)
    elif market == "US":
        roi_xarr = xr.open_dataarray(pp.DJIA_2005_NC)

    rois = roi_xarr.loc[exp_start_date:exp_end_date, symbols, 'simple_roi']

    initial_wealth = 1e6
    initial_weights = xr.DataArray(
        np.ones(n_symbol) / n_symbol,
        dims=('symbol',),
        coords=(symbols,)
    )
    obj = BAHPortfolio(
        group_name,
        symbols,
        rois,
        initial_weights,
        initial_wealth,
        start_date=exp_start_date,
        end_date=exp_end_date
    )
    obj.run()


def get_bah_report(report_dir=pp.WEIGHT_PORTFOLIO_REPORT_DIR):
    import arch.bootstrap.multiple_comparison as arch_comp

    group_names = pp.GROUP_SYMBOLS.keys()
    with open(os.path.join(pp.TMP_DIR, "BAH_stat.csv"), "w",
              newline='') as csv_file:
        fields = [
            "simulation_name",
            "group_name",
            "start_date",
            "end_date",
            "n_data",
            "cum_roi",
            "annual_roi",
            "roi_mu",
            "std",
            "skew",
            "ex_kurt",
            "Sharpe",
            "Sortino_full",
            "Sortino_partial",
            "SPA_c"
        ]

        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()

        for gdx, group_name in enumerate(group_names):
            report_name = "report_BAH_{}_20050103_20181228.pkl".format(
                group_name)

            rp = pd.read_pickle(os.path.join(pp.WEIGHT_PORTFOLIO_REPORT_DIR,
                                             report_name))

            rois = rp['decision_xarr'].loc[:, :, 'wealth'].sum(
                axis=1).to_series().pct_change()
            rois[0] = 0

            spa_value = 0
            for _ in range(3):
                spa = arch_comp.SPA(rois.values, np.zeros(rois.size),
                                    reps=1000)
                spa.seed(np.random.randint(0, 2 ** 31 - 1))
                spa.compute()
                # preserve the worse p_value
                if spa.pvalues[1] > spa_value:
                    spa_value = spa.pvalues[1]

            writer.writerow(
                {
                    "simulation_name": rp["simulation_name"],
                    "group_name": group_name,
                    "start_date": rp['exp_start_date'].strftime("%Y-%m-%d"),
                    "end_date": rp['exp_end_date'].strftime("%Y-%m-%d"),
                    "n_data": rp['n_exp_period'],
                    "cum_roi": rp['cum_roi'],
                    "annual_roi": rp['annual_roi'],
                    "roi_mu": rp['daily_mean_roi'],
                    "std": rp['daily_std_roi'],
                    "skew": rp['daily_skew_roi'],
                    "ex_kurt": rp['daily_ex-kurt_roi'],
                    "Sharpe": rp['Sharpe'],
                    "Sortino_full": rp['Sortino_full'],
                    "Sortino_partial": rp['Sortino_partial'],
                    "SPA_c": spa_value
                }
            )
            print(
                "[{}/{}] {}, cum_roi:{:.2%}".format(
                    gdx + 1, len(group_names), group_name, rp['cum_roi']
                )
            )


if __name__ == '__main__':
    logging.basicConfig(
        stream=sys.stdout,
        format='%(filename)15s %(levelname)10s %(asctime)s\n'
               '%(message)s',
        datefmt='%Y%m%d-%H:%M:%S',
        level=logging.INFO)

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--simulation", default=False,
                        action='store_true',
                        help="BAH experiment")

    parser.add_argument("-g", "--group_name", type=str,
                        help="target group")

    parser.add_argument("--stat", default=False,
                        action='store_true',
                        help="BAH experiment statistics")

    args = parser.parse_args()
    if args.simulation:
        if args.group_name:
            run_bah('dissertation', args.group_name,
                    dt.date(2005, 1, 1), dt.date(2018, 12, 28))
        else:
            import multiprocess as mp
            n_cpu = mp.cpu_count() // 2 if mp.cpu_count() >= 2 else 1
            pool = mp.Pool(processes=n_cpu)
            results = [pool.apply_async(run_bah,
                                        ('dissertation', group_name,
                                         dt.date(2005, 1, 1),
                                         dt.date(2018, 12, 28)
                                         ))
                       for group_name in pp.GROUP_SYMBOLS.keys()
                       ]
            [result.wait() for result in results]
            pool.close()
            pool.join()

            # for group_name in pp.GROUP_SYMBOLS.keys():
            #     run_bah('dissertation', group_name,
            #             dt.date(2005, 1, 1), dt.date(2018, 12, 28))
            if args.stat:
                get_bah_report()
