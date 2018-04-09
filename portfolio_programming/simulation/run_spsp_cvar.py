# -*- coding: utf-8 -*-
"""
Author: Hung-Hsin Chen <chenhh@par.cse.nsysu.edu.tw>
License: GPL v3

The SPSP CVaR experiments are not able to run in parallel setting(ipyparallel)
because ofthe complex setting of pyomo.
"""

import datetime as dt
import json
import logging
import os
import sys

import numpy as np
import xarray as xr

import portfolio_programming as pp
import portfolio_programming.simulation.spsp_cvar


def run_SPSP_CVaR(setting, scenario_set_idx, exp_start_date, exp_end_date,
                  symbols, max_portfolio_size, rolling_window_size,
                  alpha, n_scenario):
    risky_roi_xarr = xr.open_dataarray(
        pp.TAIEX_2005_LARGESTED_MARKET_CAP_DATA_NC)

    if setting == 'compact':
        candidate_symbols = symbols[:max_portfolio_size]
    else:
        candidate_symbols = symbols

    n_symbol = len(candidate_symbols)
    risky_rois = risky_roi_xarr.loc[exp_start_date:exp_end_date,
                 candidate_symbols, 'simple_roi']

    exp_trans_dates = risky_rois.get_index('trans_date')
    n_exp_dates = len(exp_trans_dates)
    risk_free_rois = xr.DataArray(np.zeros(n_exp_dates),
                                  coords=(exp_trans_dates,))
    initial_risk_wealth = xr.DataArray(np.zeros(n_symbol),
                                       dims=('symbol',),
                                       coords=(candidate_symbols,))
    initial_risk_free_wealth = 1e6
    print(setting, exp_start_date, exp_end_date, max_portfolio_size,
          rolling_window_size, alpha, n_scenario)
    instance = portfolio_programming.simulation.spsp_cvar.SPSP_CVaR(
        candidate_symbols,
        setting,
        max_portfolio_size,
        risky_rois,
        risk_free_rois,
        initial_risk_wealth,
        initial_risk_free_wealth,
        start_date=exp_trans_dates[0],
        end_date=exp_trans_dates[-1],
        rolling_window_size=rolling_window_size,
        alpha=alpha,
        n_scenario=n_scenario,
        scenario_set_idx=scenario_set_idx,
        print_interval=10
    )
    instance.run()


def plot_2d_contour_by_alpha(setting, z_dim="cum_roi"):
    """
    The  2 x 5 contour diagrams in the paper are generated by the function
    """

    # verify setting
    if setting not in ("compact", "general"):
        raise ValueError("unknown setting: {}".format(setting))

    start_date, end_date = dt.date(2005, 1, 3), dt.date(2014, 12, 31)
    name = "report_SPSP_CVaR_whole_{}_{}_{}.nc".format(
        setting, start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"))
   
    # read report file
    xarr = xr.open_dataarray(open(os.path.join(pp.DATA_DIR, name), 'rb'))

    # parameters
    max_portfolio_sizes = range(5, 50 + 5, 5)
    window_sizes = range(60, 240 + 10, 10)
    alphas = ["{:.2f}".format(v / 100.) for v in range(50, 100, 5)]
    set_indices = [1, 2, 3]

    import matplotlib as mpl
    import matplotlib.pyplot as plt

    # figure size in inches
    fig = plt.figure(figsize=(64, 48), facecolor='white')

    # set color range
    if z_dim == 'cum_roi':
        cm_norm = mpl.colors.Normalize(vmin=-100, vmax=300, clip=False)
        color_range = np.arange(-100, 300 + 10, 20)
    elif z_dim == "daily_VSS":
        cm_norm = mpl.colors.Normalize(vmin=0, vmax=4, clip=False)
        color_range = np.arange(0, 4 + 0.2, 0.3)

    xlim = (5, 50)
    ylim = (60, 240)
    for adx, alpha in enumerate(alphas):
        # x-axis, max_portfolio_size, y-axis:  window_sizes
        ax = fig.add_subplot(2, 5, adx + 1, xlim=xlim, ylim=ylim)

        ax.set_title(r'$\alpha$ = {:.0%}'.format(float(alpha)),
                     y=1.02, fontsize=18)
        # labelpad - number of points between the axis and its label
        ax.set_xlabel(r'$M$', fontsize=14, labelpad=-2,
                      fontname="Times New Roman")
        ax.set_ylabel(r'$h$', fontsize=14, labelpad=-2,
                      fontname="Times New Roman")
        ax.tick_params(labelsize=10, pad=1)
        ax.set_xticks(max_portfolio_sizes)
        ax.set_xticklabels(max_portfolio_sizes, fontsize=10,
                           fontname="Times New Roman")
        ax.set_yticks(window_sizes)
        ax.set_yticklabels(window_sizes, fontsize=10,
                           fontname="Times New Roman")

        Xs, Ys = np.meshgrid(max_portfolio_sizes, window_sizes)
        Zs = np.zeros_like(Xs, dtype=np.float)
        n_row, n_col = Xs.shape

        for rdx in range(n_row):
            for cdx in range(n_col):
                n_symbol, win_size = Xs[rdx, cdx], Ys[rdx, cdx]
                z_values = xarr.loc[
                    "{}_{}".format(start_date.strftime("%Y%m%d"),
                                   end_date.strftime("%Y%m%d")),
                    set_indices, n_symbol, win_size,
                    alpha, z_dim]
                mean = z_values.mean()
                Zs[rdx, cdx] = float(mean) * 100.

        print("Z_dim:", z_dim)
        print("z_range:", np.min(Zs), np.max(Zs))
        print(Zs)
        # contour, projecting on z
        cset = ax.contourf(Xs, Ys, Zs,
                           cmap=plt.cm.coolwarm,
                           norm=cm_norm,
                           levels=color_range)

    # share color bar,  rect [left, bottom, width, height]
    cbar_ax = fig.add_axes([0.92, 0.125, 0.015, 0.75])
    # print fig.get_axes()
    cbar = fig.colorbar(cset, ax=fig.get_axes(), cax=cbar_ax,
                        ticks=color_range)

    cbar.ax.tick_params(labelsize=12)
    if z_dim == "cum_roi":
        cbar_label_name = "Average cumulative returns (%)"
    elif z_dim == "daily_VSS":
        cbar_label_name = "Average daily VSS (%)"

    cbar.set_label(cbar_label_name, labelpad=1, size=20,
                   fontname="Times New Roman")

    plt.show()

def plot_yearly_2d_contour_by_alpha(setting, z_dim="cum_roi"):
    # verify setting
    if setting not in ("compact", "general"):
        raise ValueError("unknown setting: {}".format(setting))


    start_date, end_date = dt.date(2005, 1, 3), dt.date(2017, 12, 29)
    name = "report_SPSP_CVaR_yearly_{}_{}_{}.nc".format(
        setting, start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"))

    # yearly interval
    years = [[dt.date(2005, 1, 3), dt.date(2005, 12, 30)],
             [dt.date(2006, 1, 2), dt.date(2006, 12, 29)],
             [dt.date(2007, 1, 2), dt.date(2007, 12, 31)],
             [dt.date(2008, 1, 2), dt.date(2008, 12, 31)],
             [dt.date(2009, 1, 5), dt.date(2009, 12, 31)],
             [dt.date(2010, 1, 4), dt.date(2010, 12, 31)],
             [dt.date(2011, 1, 3), dt.date(2011, 12, 30)],
             [dt.date(2012, 1, 2), dt.date(2012, 12, 28)],
             [dt.date(2013, 1, 2), dt.date(2013, 12, 31)],
             [dt.date(2014, 1, 2), dt.date(2014, 12, 31)],
             [dt.date(2015, 1, 5), dt.date(2015, 12, 31)],
             [dt.date(2016, 1, 4), dt.date(2016, 12, 30)],
             [dt.date(2017, 1, 3), dt.date(2017, 12, 29)]
             ]

    # read report file
    xarr = xr.open_dataarray(open(os.path.join(pp.DATA_DIR, name), 'rb'))

    # parameters
    max_portfolio_sizes = range(5, 50 + 5, 5)
    window_sizes = range(60, 240 + 10, 10)
    alphas = ["{:.2f}".format(v / 100.) for v in range(50, 100, 5)]
    set_indices = [1, 2, 3]

    import matplotlib as mpl
    import matplotlib.pyplot as plt

    for start, end in years:
        # figure size in inches
        fig = plt.figure(figsize=(64, 48), facecolor='white')
        fig.suptitle('TAIEX_20050103_50largest_listed_market_cap {} {}-{}'.format(
            setting, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")),
            fontsize=20)


        xlim = (5, 50)
        ylim = (60, 240)
        for adx, alpha in enumerate(alphas):
            # x-axis, max_portfolio_size, y-axis:  window_sizes
            ax = fig.add_subplot(2, 5, adx + 1, xlim=xlim, ylim=ylim)

            ax.set_title(r'$\alpha$ = {:.0%}'.format(float(alpha)),
                         y=1.02, fontsize=18)
            # labelpad - number of points between the axis and its label
            ax.set_xlabel(r'$M$', fontsize=14, labelpad=-2,
                          fontname="Times New Roman")
            ax.set_ylabel(r'$h$', fontsize=14, labelpad=-2,
                          fontname="Times New Roman")
            ax.tick_params(labelsize=10, pad=1)
            ax.set_xticks(max_portfolio_sizes)
            ax.set_xticklabels(max_portfolio_sizes, fontsize=10,
                               fontname="Times New Roman")
            ax.set_yticks(window_sizes)
            ax.set_yticklabels(window_sizes, fontsize=10,
                               fontname="Times New Roman")

            Xs, Ys = np.meshgrid(max_portfolio_sizes, window_sizes)
            Zs = np.zeros_like(Xs, dtype=np.float)
            n_row, n_col = Xs.shape

            for rdx in range(n_row):
                for cdx in range(n_col):
                    n_symbol, win_size = Xs[rdx, cdx], Ys[rdx, cdx]
                    z_values = xarr.loc[
                        "{}_{}".format(start.strftime("%Y%m%d"),
                                       end.strftime("%Y%m%d")),
                        set_indices, n_symbol, win_size,
                        alpha, z_dim]
                    mean = z_values.mean()
                    Zs[rdx, cdx] = float(mean) * 100.
                    # if Zs[rdx, cdx] > 10:
                    #     Zs[rdx, cdx] = 10.5

            print("Z_dim:", z_dim)
            print("z_range:", np.min(Zs), np.max(Zs))
            z_min = int(np.floor(np.min(Zs)))
            z_max = int(np.ceil(np.max(Zs)))

            # set color range
            if z_dim == 'cum_roi':
                cm_norm = mpl.colors.Normalize(vmin=z_min, vmax=z_max,
                                               clip=False)
                color_range = np.arange(z_min, z_max + 1)

            # contour, projecting on z
            cset = ax.contourf(Xs, Ys, Zs,
                               cmap=plt.cm.coolwarm,
                               norm=cm_norm,
                               levels=color_range)

        # share color bar,  rect [left, bottom, width, height]
        cbar_ax = fig.add_axes([0.92, 0.125, 0.015, 0.75])
        # print fig.get_axes()
        cbar = fig.colorbar(cset, ax=fig.get_axes(), cax=cbar_ax,
                            ticks=color_range)

        cbar.ax.tick_params(labelsize=12)
        if z_dim == "cum_roi":
            cbar_label_name = "Average cumulative returns (%)"
        elif z_dim == "daily_VSS":
            cbar_label_name = "Average daily VSS (%)"

        cbar.set_label(cbar_label_name, labelpad=1, size=20,
                       fontname="Times New Roman")
        fig_path = os.path.join(pp.TMP_DIR,
                                'SPSP_CVaR_cum_roi_yearly_{}_{}.png'.format(
                                    setting, start.year))
        fig.set_size_inches(16, 9)
        plt.savefig(fig_path, dpi=240, format='png')

    plt.show()


if __name__ == '__main__':
    logging.basicConfig(
        stream=sys.stdout,
        format='%(filename)15s %(levelname)10s %(asctime)s\n'
               '%(message)s',
        datefmt='%Y%m%d-%H:%M:%S',
        level=logging.INFO)

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--setting", type=str,
                        choices=("compact", "general"),
                        help="SPSP setting")

    parser.add_argument("--year", type=int,
                        choices=range(2005, 2017 + 1),
                        help="yearly experiments")

    parser.add_argument("--symbol", type=str,
                       help="target symbol")

    parser.add_argument("-M", "--max_portfolio_size", type=int,
                        choices=range(5, 55, 5),
                        help="max_portfolio_size")

    parser.add_argument("-w", "--rolling_window_size", type=int,
                        choices=range(50, 250, 10),
                        help="rolling window size for estimating statistics.")

    parser.add_argument("-a", "--alpha", type=str,
                        choices=["{:.2f}".format(v / 100.)
                                 for v in range(50, 100, 5)],
                        help="confidence level of CVaR")

    parser.add_argument("--scenario_set_idx", type=int,
                        choices=range(1, 4),
                        default=1,
                        help="pre-generated scenario set index.")
    args = parser.parse_args()

    print("run_SPSP_CVaR in single mode")

    if args.symbol:
        candidate_symbols = [args.symbol, ]
    else:
        candidate_symbols = json.load(
           open(pp.TAIEX_2005_LARGEST4ED_MARKET_CAP_SYMBOL_JSON))

    if not args.year:
        run_SPSP_CVaR(args.setting,
                      args.scenario_set_idx,
                      '20050103', '20141231',
                      candidate_symbols,
                      args.max_portfolio_size,
                      args.rolling_window_size,
                      float(args.alpha),
                      200)
    else:
        years = {
            2005: (dt.date(2005, 1, 3), dt.date(2005, 12, 30)),
            2006: (dt.date(2006, 1, 2), dt.date(2006, 12, 29)),
            2007: (dt.date(2007, 1, 2), dt.date(2007, 12, 31)),
            2008: (dt.date(2008, 1, 2), dt.date(2008, 12, 31)),
            2009: (dt.date(2009, 1, 5), dt.date(2009, 12, 31)),
            2010: (dt.date(2010, 1, 4), dt.date(2010, 12, 31)),
            2011: (dt.date(2011, 1, 3), dt.date(2011, 12, 30)),
            2012: (dt.date(2012, 1, 2), dt.date(2012, 12, 28)),
            2013: (dt.date(2013, 1, 2), dt.date(2013, 12, 31)),
            2014: (dt.date(2014, 1, 2), dt.date(2014, 12, 31)),
            2015: (dt.date(2015, 1, 5), dt.date(2015, 12, 31)),
            2016: (dt.date(2016, 1, 4), dt.date(2016, 12, 30)),
            2017: (dt.date(2017, 1, 3), dt.date(2017, 12, 29))
        }

        run_SPSP_CVaR(args.setting,
                      args.scenario_set_idx,
                      years[args.year][0],
                      years[args.year][1],
                      candidate_symbols,
                      args.max_portfolio_size,
                      args.rolling_window_size,
                      float(args.alpha),
                      200)
