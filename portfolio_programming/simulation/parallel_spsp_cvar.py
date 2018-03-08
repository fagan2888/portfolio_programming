# -*- coding: utf-8 -*-
"""
Authors: Hung-Hsin Chen <chenhh@par.cse.nsysu.edu.tw>
License: GPL v3
"""

import os
import platform
import glob
import time
import logging
import sys
import datetime as dt
import pickle

import zmq
import numpy as np
import xarray as xr
import portfolio_programming as pp
from portfolio_programming.simulation.run_spsp_cvar import run_SPSP_CVaR


def get_zmq_version():
    node = platform.node()
    print("Node:{} libzmq version is {}".format(node, zmq.zmq_version()))
    print("Node:{} pyzmq version is {}".format(node, zmq.__version__))


def _all_spsp_cvar_params(setting):
    """
    "report_SPSP_CVaR_{}_scenario-set-idx{}_{}_{}_M{}_Mc{}_h{}_a{:.2f}_s{
    }.pkl".format(
                self.setting,
                self.scenario_set_idx,
                self.exp_start_date.strftime("%Y%m%d"),
                self.exp_end_date.strftime("%Y%m%d"),
                self.max_portfolio_size,
                self.n_symbol,
                self.rolling_window_size,
                self.alpha,
                self.n_scenario
            )
    """
    REPORT_FORMAT = "report_SPSP_CVaR_{setting}_scenario-set-idx{sdx}_{" \
                    "exp_start_date}_{exp_end_date}_M{max_portfolio}_Mc{" \
                    "n_candidate_symbol}_h{rolling_window_size" \
                    "}_a{alpha}_s{n_scenario}.pkl"
    if setting not in ('compact', 'general'):
        raise ValueError('Wrong setting: {}'.format(setting))

    # set_indices = (1, 2, 3)
    set_indices = (1, 2, 3)
    s_date = pp.SCENARIO_START_DATE.strftime("%Y%m%d")
    e_date = pp.SCENARIO_END_DATE.strftime("%Y%m%d")
    max_portfolio_sizes = range(5, 50 + 5, 5)
    window_sizes = range(60, 240 + 10, 10)
    n_scenarios = [200, ]
    alphas = ["{:.2f}".format(v / 100.) for v in range(50, 100, 5)]

    # dict comprehension
    # key: file_name, value: parameters
    if setting == "compact":
        return {
            REPORT_FORMAT.format(
                setting=setting,
                sdx=sdx,
                exp_start_date=s_date,
                exp_end_date=e_date,
                max_portfolio=m,
                n_candidate_symbol=m,
                rolling_window_size=h,
                alpha=a,
                n_scenario=s
            ): (setting, sdx, s_date, e_date, m, h, float(a), s)
            for sdx in set_indices
            for m in max_portfolio_sizes
            for h in window_sizes
            for a in alphas
            for s in n_scenarios
        }

    elif setting == "general":
        return {
            REPORT_FORMAT.format(
                setting=setting,
                sdx=sdx,
                exp_start_date=s_date,
                exp_end_date=e_date,
                max_portfolio=m,
                n_candidate_symbol=50,
                rolling_window_size=h,
                alpha=a,
                n_scenario=s
            ): (setting, sdx, s_date, e_date, m, h, float(a), s)
            for sdx in set_indices
            for m in max_portfolio_sizes
            for h in window_sizes
            for a in alphas
            for s in n_scenarios
        }


def checking_existed_spsp_cvar_report(setting, report_dir=None):
    """
    return unfinished experiment parameters.
    """
    if report_dir is None:
        report_dir = pp.REPORT_DIR
    all_reports = _all_spsp_cvar_params(setting)

    os.chdir(report_dir)
    existed_reports = glob.glob("*.pkl")
    for report in existed_reports:
        all_reports.pop(report, None)

    # unfinished params
    return all_reports


def parameters_server(setting="compact"):
    node = platform.node()
    pid = os.getpid()
    context = zmq.Context()

    # zmq.sugar.socket.Socket
    socket = context.socket(zmq.REP)

    # Protocols supported include tcp, udp, pgm, epgm, inproc and ipc.
    socket.bind("tcp://*:25555")

    params = set(checking_existed_spsp_cvar_report(setting).values())
    workers = {}
    while len(params):
        # Wait for request from client
        client_node_pid = socket.recv_string()
        print("{:<15} Received request: {}".format(
            str(dt.datetime.now()),
            client_node_pid))
        node, pid = client_node_pid.split('_')
        workers.setdefault(node, 0)
        workers[node] += 1

        #  Send reply back to client
        work = params.pop()
        print("send {} to {}".format(work, client_node_pid))
        socket.send_pyobj(params.pop())

        print("unfinished parameters:{}".format(len(params)))
        for node, cnt in workers.items():
            print("node:{:<8} finish {:>3}".format(node, cnt))

    socket.close()
    context.term()


def parameter_client(server_ip="140.117.168.49"):
    node = platform.node()
    pid = os.getpid()

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    url = "tcp://{}:25555".format(server_ip)
    socket.connect(url)

    # for IO monitoring
    poll = zmq.Poller()
    poll.register(socket, zmq.POLLIN)

    node_pid = "{}_{}".format(node, pid)
    while True:
        # send request to server
        socket.send_string(node_pid)
        socks = dict(poll.poll(10000))

        if socks.get(socket) == zmq.POLLIN:
            # still connected
            # receive parameters from server
            work = socket.recv_pyobj()
            print("{:<15} receiving: {}".format(
                str(dt.datetime.now()),
                work))
            run_SPSP_CVaR(*work)

        else:
            # no response from server, reconnected
            socket.setsockopt(zmq.LINGER, 0)
            socket.close()
            poll.unregister(socket)

            # reconnection
            socket = context.socket(zmq.REQ)
            socket.connect(url)
            poll.register(socket, zmq.POLLIN)

            socket.send_string(node_pid)
            print('reconnect to {}'.format(url))

    socket.close()
    context.term()


def aggregating_reports(setting="compact"):
    s_date = pp.SCENARIO_START_DATE.strftime("%Y%m%d")
    e_date = pp.SCENARIO_END_DATE.strftime("%Y%m%d")
    max_portfolio_sizes = range(5, 50 + 5, 5)
    window_sizes = range(60, 240 + 10, 10)
    n_scenarios = [200, ]
    alphas = ["{:.2f}".format(v / 100.) for v in range(50, 100, 5)]

    attributes = [
        'initial_wealth', 'final_wealth',
        'cum_roi', 'daily_roi', 'daily_mean_roi',
        'daily_std_roi', 'daily_skew_roi', 'daily_ex-kurt_roi',
        'Sharpe', 'Sortino_full', 'Sortino_partial'
    ]
    report_xarr = xr.DataArray(
        np.zeros((
            len(max_portfolio_sizes), len(window_sizes), len(alphas),
            len(attributes))),
        dims=("max_portfolio_size", "rolling_window_size",
              "alpha", "attribute"),
        coords=(max_portfolio_sizes, window_sizes, alphas,
                attributes)
    )

    report_names = _all_spsp_cvar_params(setting).keys()

    for name in report_names:
        path = os.path.join(pp.REPORT_DIR, name)
        try:
            with open(path, 'rb') as fin:
                report = pickle.load(fin)
                print(report['simulation_name'], report['cum_roi'])
        except FileNotFoundError as e:
            print("{} does not exists.".format(name))
            continue





if __name__ == '__main__':
    logging.basicConfig(
        stream=sys.stdout,
        format='%(filename)15s %(levelname)10s %(asctime)s\n'
               '%(message)s',
        datefmt='%Y%m%d-%H:%M:%S',
        level=logging.INFO)
    import argparse

    get_zmq_version()

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("-s", "--server", default=False,
                        action='store_true',
                        help="parameter server mode")

    parser.add_argument("-c", "--client", default=False,
                        action='store_true',
                        help="run SPSP_CVaR client mode")

    parser.add_argument("--compact_report", default=False,
                        action="store_true",
                        help="SPSP_CVaR compact setting report")

    args = parser.parse_args()
    if args.server:
        print("run SPSP_CVaR parameter server mode")
        parameters_server()
    elif args.client:
        print("run SPSP_CVaR client mode")
        parameter_client()
    elif args.compact_report:
        print("SPSP CVaR compact setting report")
        aggregating_reports("compact")
    else:
        raise ValueError("no mode is set.")