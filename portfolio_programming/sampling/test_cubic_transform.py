# -*- coding: utf-8 -*-
"""
Author: Hung-Hsin Chen <chen1116@gmail.com>
"""

import numpy as np
import scipy.stats as spstats
from portfolio_programming.sampling.cubic_transform_sampling import (
    cubic_transform_sampling,)


def statistics(samples):
    return "{:.2f} {:.2f} {:.2f} {:.2f}".format(
        samples.mean(),
        samples.std(ddof=1),
        spstats.skew(samples, bias=False),
        spstats.kurtosis(samples, bias=False))


def plot_samples():
    import scipy.special as spsp
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(5)

    mu, std, skew, ex_kurt = 10, 3, 0, 0
    samples = cubic_transform_sampling(np.asarray([mu, std, skew, ex_kurt],
                                                  dtype=np.float))
    axes[0].set_title('normal')
    x = np.linspace(-20, 20, len(samples))
    y = 1 / np.sqrt(2 * np.pi * std * std) * np.exp(
        -(x - mu) * (x - mu) / (2 * std * std))

    axes[0].plot(x, y, color="green", lw=2)
    axes[0].hist(samples, bins=100, normed=True)
    print(statistics(samples))

    # student(nu)
    nu = 8.
    mu, std, skew, ex_kurt = 0, np.sqrt(nu / (nu - 2)), 0, 6 / (nu - 4)
    samples = cubic_transform_sampling(np.asarray([mu, std, skew, ex_kurt]))
    axes[1].set_title('student(nu={})'.format(nu))
    x = np.linspace(-20, 20, len(samples))
    y = spsp.gamma((nu + 1) / 2) / np.sqrt(nu * np.pi) / spsp.gamma(nu / 2) * (
            1 + x * x / nu) ** (-(nu + 1) / 2)

    axes[1].plot(x, y, color="green", lw=2)
    axes[1].hist(samples, bins=100, normed=True)
    print(statistics(samples))

    # chi-square(k)
    chi_k = 8.
    half_k = chi_k / 2
    samples = cubic_transform_sampling(np.asarray([chi_k, np.sqrt(2 * chi_k), np.sqrt(
        8 / chi_k), 12 / chi_k]))
    axes[2].set_title('chi_square(k={}))'.format(chi_k))
    x = np.linspace(0, 20, len(samples))
    y = 1 / (2 ** (half_k) * spsp.gamma(half_k)) * x ** (half_k - 1) * np.exp(
        -x / 2)

    axes[2].plot(x, y, color="green", lw=2)
    axes[2].hist(samples, bins=100, normed=True)
    print(statistics(samples))

    # gamma(k, theta)
    k = 10
    theta = 1
    samples = cubic_transform_sampling(np.asarray([k * theta,
                                        np.sqrt(k * theta * theta),
                                        2 / np.sqrt(k),
                                        6. / k
                                        ]))
    axes[3].set_title('Gamma(k,theta)=({}, {:.2f})'.format(k, theta))
    x = np.linspace(0, 20, len(samples))
    y = 1 / (spsp.gamma(k) * theta ** k) * x ** (k - 1) * np.exp(-x / theta)

    axes[3].plot(x, y, color="green", lw=2)
    axes[3].hist(samples, bins=100, normed=True)
    print(statistics(samples))

    # Boltzmann
    a = 10
    samples = cubic_transform_sampling(np.asarray([2*a*(2/np.pi)**0.5,
                                        np.sqrt(a*a*(3*np.pi-8)/np.pi),
                                        2*2**0.5*(16-5*np.pi)/(3*np.pi-8)**1.5,
                                        4*(-96+40*np.pi-3*np.pi**2)/(
                                                3*np.pi-8)**2
                                        ]))
    x = np.linspace(0, 20, len(samples))
    y = (2 / np.pi) ** 0.5 * x**2 * np.exp(-x**2 * 0.5 / a / a) / a ** 3
    axes[4].plot(x, y, color="green", lw=2)
    axes[4].hist(samples, bins=100, normed=True)
    print(statistics(samples))

    plt.show()


if __name__ == '__main__':
    plot_samples()