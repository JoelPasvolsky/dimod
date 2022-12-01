# -*- coding: utf-8 -*-
# Copyright 2022 D-Wave Systems Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, 
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
# ===============================================================================================

#Author: Jack Raymond
#Date: December 18th 2020

import numpy as np
import dimod 
from itertools import product
from typing import Callable, Sequence, Union, Iterable
import networkx as nx

def _quadratic_form(y, F):
    '''Convert O(v) = ||y - F v||^2 to a sparse quadratic form, where
    y, F are assumed to be complex or real valued.

    Constructs coefficients for the form O(v) = v^dag J v - 2 Re [h^dag vD] + k
    
    Inputs
        v: column vector of complex values
        y: column vector of complex values
        F: matrix of complex values
    Output
        k: real scalar
        h: dense real vector
        J: dense real symmetric matrix
    
    '''
    if len(y.shape) != 2 or y.shape[1] != 1:
        raise ValueError('y should have shape [n, 1] for some n')
    if len(F.shape) != 2 or F.shape[0] != y.shape[0]:
        raise ValueError('F should have shape [n, m] for some m, n'
                         'and n should equal y.shape[1]')

    offset = np.matmul(y.imag.T, y.imag) + np.matmul(y.real.T, y.real)
    h = - 2*np.matmul(F.T.conj(), y) ## Be careful with interpretaion!
    J = np.matmul(F.T.conj(), F) 

    return offset, h, J

def _real_quadratic_form(h, J, modulation=None):
    '''Unwraps objective function on complex variables onto objective
    function of concatenated real variables: the real and imaginary
    parts.
    '''
    if modulation != 'BPSK' and (h.dtype == np.complex128 or J.dtype == np.complex128):
        hR = np.concatenate((h.real, h.imag), axis=0)
        JR = np.concatenate((np.concatenate((J.real, J.imag), axis=0), 
                            np.concatenate((J.imag.T, J.real), axis=0)), 
                           axis=1)
        return hR, JR
    else:
        return h.real, J.real

def _amplitude_modulated_quadratic_form(h, J, modulation):
    if modulation == 'BPSK' or modulation == 'QPSK':
        #Easy case, just extract diagonal
        return h, J
    else:
        #Quadrature + amplitude modulation
        if modulation == '16QAM':
            num_amps = 2
        elif modulation == '64QAM':
            num_amps = 3
        else:
            raise ValueError('unknown modulation')
        amps = 2**np.arange(num_amps)
        hA = np.kron(amps[:, np.newaxis], h)
        JA = np.kron(np.kron(amps[:, np.newaxis], amps[np.newaxis, :]), J)
        return hA, JA 

    
    
def symbols_to_spins(symbols: np.array, modulation: str) -> np.array:
    "Converts binary/quadrature amplitude modulated symbols to spins, assuming linear encoding"
    num_transmitters = len(symbols)
    if modulation == 'BPSK':
        return symbols.copy()
    else:
        if modulation == 'QPSK':
            # spins_per_real_symbol = 1
            return np.concatenate((symbols.real, symbols.imag))
        elif modulation == '16QAM':
            spins_per_real_symbol = 2
        elif modulation == '64QAM':
            spins_per_real_symbol = 3
        else:
            raise ValueError('Unsupported modulation')
        # A map from integer parts to real is clearest (and sufficiently performant), 
        # generalizes to gray code more easily as well:
        
        symb_to_spins = { np.sum([x*2**xI for xI, x in enumerate(spins)]) : spins
                          for spins in product(*[(-1, 1) for x in range(spins_per_real_symbol)])}
        spins = np.concatenate([np.concatenate(([symb_to_spins[symb][prec] for symb in symbols.real.flatten()], 
                                                [symb_to_spins[symb][prec] for symb in symbols.imag.flatten()]))
                                for prec in range(spins_per_real_symbol)])
        if len(symbols.shape)>2:
            if symbols.shape[0] == 1:
                # If symbols shaped as vector, return as vector:
                spins.reshape((1,len(spins)))
            elif symbols.shape[1] == 1:
                spins.reshape((len(spins),1))
            else:
                # Leave for manual reshaping
                pass 
    return spins


def _yF_to_hJ(y, F, modulation):
    offset, h, J = _quadratic_form(y, F) # Quadratic form re-expression
    h, J = _real_quadratic_form(h, J, modulation) # Complex symbols to real symbols (if necessary)
    h, J = _amplitude_modulated_quadratic_form(h, J, modulation) # Real symbol to linear spin encoding
    return h, J, offset

def linear_filter(F, method='zero_forcing', SNRoverNt=float('Inf'), PoverNt=1):
    """ Construct linear filter W for estimation of transmitted signals.
    # https://www.youtube.com/watch?v=U3qjVgX2poM
   
    
    We follow conventions laid out in MacKay et al. 'Achievable sum rate of MIMO MMSE receivers: A general analytic framework'
    N0 Identity[N_r] = E[n n^dagger]
    P/N_t Identify[N_t] = E[v v^dagger], i.e. P = constellation_mean_power*Nt for i.i.d elements (1,2,10,42)Nt for BPSK, QPSK, 16QAM, 64QAM.
    N_r N_t = E_F[Tr[F Fdagger]], i.e. E[||F_{mu,i}||^2]=1 for i.i.d channel.  - normalization is assumed to be pushed into symbols.
    SNRoverNt = PoverNt/N0 : Intensive quantity. 
    SNRb = SNR/(Nt*bits_per_symbol)

    Typical use case: set SNRoverNt = SNRb
    """
    
    if method == 'zero_forcing':
        # Moore-Penrose pseudo inverse
        W = np.linalg.pinv(F)
    else:
        Nr, Nt = F.shape
         # Matched Filter
        if method == 'matched_filter':
            W = F.conj().T/ np.sqrt(PoverNt)
            # F = root(Nt/P) Fcompconj
        elif method == 'MMSE':
            W = np.matmul(F.conj().T, np.linalg.pinv(np.matmul(F,F.conj().T) + np.identity(Nr)/SNRoverNt))/np.sqrt(PoverNt)
        else:
            raise ValueError('Unsupported linear method')
    return W
    
def filter_marginal_estimator(x: np.array, modulation: str):
    if modulation is not None:
        if modulation == 'BPSK' or modulation == 'QPSK':
            max_abs = 1
        elif modulation == '16QAM':
            max_abs = 3
        elif modulation == '64QAM':
            max_abs = 7
        elif modulation == '128QAM':
            max_abs = 15
        else:
            raise ValueError('Unknown modulation')
        #Real part (nearest):
        x_R = 2*np.round((x.real-1)/2)+1
        x_R = np.where(x_R<-max_abs,-max_abs,x_R)
        x_R = np.where(x_R>max_abs,max_abs,x_R)
        if modulation != 'BPSK':
            x_I = 2*np.round((x.imag-1)/2)+1
            x_I = np.where(x_I<-max_abs,-max_abs,x_I)
            x_I = np.where(x_I>max_abs,max_abs,x_I)
            return x_R + 1j*x_I
        else:
            return x_R
        
def spins_to_symbols(spins: np.array, modulation: str = None, num_transmitters: int = None) -> np.array:
    "Converts spins to modulated symbols assuming a linear encoding"
    num_spins = len(spins)
    if num_transmitters is None:
        if modulation == 'BPSK':
            num_transmitters = num_spins
        elif modulation == 'QPSK':
            num_transmitters = num_spins//2
        elif modulation == '16QAM':
            num_transmitters = num_spins//4
        elif modulation == '64QAM':
            num_transmitters = num_spins//6
        else:
            raise ValueError('Unsupported modulation')
        
    if num_transmitters == num_spins:
        symbols = spins 
    else:
        num_amps, rem = divmod(len(spins), (2*num_transmitters))
        if num_amps > 64:
            raise ValueError('Complex encoding is limited to 64 bits in'
                             'real and imaginary parts; num_transmitters is'
                             'too small')
        if rem != 0:
            raise ValueError('num_spins must be divisible by num_transmitters '
                             'for modulation schemes')
        
        spinsR = np.reshape(spins, (num_amps, 2*num_transmitters))
        amps = 2**np.arange(0, num_amps)[:, np.newaxis]
        
        symbols = np.sum(amps*spinsR[:, :num_transmitters], axis=0) \
                + 1j * np.sum(amps*spinsR[:, num_transmitters:], axis=0)
    return symbols

def create_channel(num_receivers, num_transmitters, F_distribution=None, random_state=None):
    """Create a channel model. Channel power is the expected root mean square signal per receiver. I.e. mean(F^2)*num_transmitters for homogeneous codes."""
    channel_power = 1
    if random_state is None:
        random_state = np.random.RandomState(random_state) 
    if F_distribution is None:
        F_distribution = ('Normal', 'Complex')
    elif type(F_distribution) is not tuple or len(F_distribution) !=2:
        raise ValueError('F_distribution should be a tuple of strings or None')
    if F_distribution[0] == 'Normal':
        if F_distribution[1] == 'Real':
            F = random_state.normal(0, 1, size=(num_receivers, num_transmitters))
        else:
            channel_power = 2
            F = random_state.normal(0, 1, size=(num_receivers, num_transmitters)) + 1j*random_state.normal(0, 1, size=(num_receivers, num_transmitters))
    elif F_distribution[0] == 'Binary':
        if F_distribution[1] == 'Real':
            F = (1-2*random_state.randint(2, size=(num_receivers, num_transmitters)))
        else:
            channel_power = 2 #For integer precision purposes:
            F = (1-2*random_state.randint(2, size=(num_receivers, num_transmitters))) + 1j*(1-2*random_state.randint(2, size=(num_receivers, num_transmitters)))
    return F, channel_power*num_transmitters


def constellation_properties(modulation):
    """ bits per symbol, constellation mean power, and symbol amplitudes. 
    
    The constellation mean power assumes symbols are sampled uniformly at
    random for the signal (standard).
    """
    
    if modulation == 'BPSK':
        bits_per_transmitter = 1
        constellation_mean_power = 1
        amps = np.ones(1)
    else:
        bits_per_transmitter = 2
        if modulation == 'QPSK':
            amps = np.ones(1)
        elif modulation == '16QAM':
            amps = 1+2*np.arange(2)
            bits_per_transmitter *= 2
        elif modulation == '64QAM':
            amps = 1+2*np.arange(4)
            bits_per_transmitter *= 3
        elif modulation == '256QAM':
            amps = 1+2*np.arange(8)
            bits_per_transmitter *= 4
        else:
            raise ValueError('Unsupported modulation method')
        constellation_mean_power = 2*np.mean(amps*amps)
    return bits_per_transmitter, amps, constellation_mean_power

def create_transmitted_symbols(num_transmitters, amps: Iterable = [-1,1],quadrature: bool = True):
    """Symbols are generated uniformly at random as a funtion of the quadrature and amplitude modulation. 
    Note that the power per symbol is not normalized. The signal power is thus proportional to 
    Nt*sig2; where sig2 = [1,2,10,42] for BPSK, QPSK, 16QAM and 64QAM respectively. The complex and 
    real valued parts of all constellations are integer.
    
    """
    if quadrature == False:
        transmitted_symbols = np.random.choice(amps, size=(num_transmitters, 1))
    else: 
        transmitted_symbols = np.random.choice(amps, size=(num_transmitters, 1)) \
                            + 1j * np.random.choice(amps, size=(num_transmitters, 1))
    return transmitted_symbols

def create_signal(F, transmitted_symbols=None, channel_noise=None,
                  SNRb=float('Inf'), modulation='BPSK', channel_power=None,
                  random_state=None, F_norm = 1, v_norm = 1):
    """ Creates a signal y = F v + n; generating random transmitted symbols and noise as necessary. 
    F is assumed to consist of i.i.d elements such that Fdagger*F = Nr Identity[Nt]*channel_power. 
    v are assumed to consist of i.i.d unscaled constellations elements (integer valued in real
    and complex parts). mean_constellation_power dictates a rescaling relative to E[v v^dagger] = Identity[Nt]
    channel_noise is assumed, or created to be suitably scaled. N0 Identity[Nt] =  
    SNRb = /
    """
    
    num_receivers = F.shape[0]
    num_transmitters = F.shape[1] 
    if channel_power == None:
        #Assume its proportional to num_transmitters:
        channel_power = num_transmitters
    bits_per_transmitter, amps, constellation_mean_power = constellation_properties(modulation)
    if transmitted_symbols is None:
        if random_state is None:
            random_state = np.random.RandomState(random_state)
        if modulation == 'BPSK':
            transmitted_symbols = create_transmitted_symbols(num_transmitters,amps=amps,quadrature=False)
        else:
            transmitted_symbols = create_transmitted_symbols(num_transmitters,amps=amps,quadrature=True)
    if SNRb <= 0:
       raise ValueError(f"Expect positive signal to noise ratio. SNRb={SNRb}")
    elif SNRb < float('Inf'):
        # Energy_per_bit:
        Eb = channel_power*constellation_mean_power/bits_per_transmitter #Eb is the same for QPSK and BPSK
        # Eb/N0 = SNRb (N0 = 2 sigma^2, the one-sided PSD ~ kB T at antenna)
        # SNRb and Eb, together imply N0
        N0 = Eb/SNRb
        sigma = np.sqrt(N0/2) # Noise is complex by definition, hence 1/2 power in real and complex parts
        if channel_noise is None:
            
            if random_state is None:
                random_state = np.random.RandomState(random_state)
            # Channel noise of covariance N0* I_{NR}. Noise is complex by definition, although
            # for real channel and symbols we need only worry about real part:
            if transmitted_symbols.dtype==np.float64 and F.dtype==np.float64:
                channel_noise = sigma*random_state.normal(0, 1, size=(num_receivers, 1))
                # Complex part is irrelevant
            else:
                channel_noise = sigma*(random_state.normal(0, 1, size=(num_receivers, 1)) \
                                       + 1j*random_state.normal(0, 1, size=(num_receivers, 1)))
            
        y = channel_noise + np.matmul(F, transmitted_symbols)
    else:
        y = np.matmul(F, transmitted_symbols)
    
    return y, transmitted_symbols, channel_noise, random_state

def spin_encoded_mimo(modulation: str, y: Union[np.array, None] = None, F: Union[np.array, None] = None,
                      *,
                      transmitted_symbols: Union[np.array, None] = None, channel_noise: Union[np.array, None] = None, 
                      num_transmitters: int = None,  num_receivers: int = None, SNRb: float = float('Inf'), 
                      seed: Union[None, int, np.random.RandomState] = None, 
                      F_distribution: Union[None, tuple] = None, 
                      use_offset: bool = False) -> dimod.BinaryQuadraticModel:
    """ Generate a multi-input multiple-output (MIMO) channel-decoding problem.
        
    Users each transmit complex valued symbols over a random channel :math:`F` of 
    some num_receivers, subject to additive white Gaussian noise. Given the received
    signal y the log likelihood of a given symbol set :math:`v` is given by 
    :math:`MLE = argmin || y - F v ||_2`. When v is encoded as a linear
    sum of spins the optimization problem is defined by a Binary Quadratic Model. 
    Depending on arguments used, this may be a model for Code Division Multiple
    Access _[#T02, #R20], 5G communication network problems _[#Prince], or others.
    
    Args:
        y: A complex or real valued signal in the form of a numpy array. If not
            provided, generated from other arguments.

        F: A complex or real valued channel in the form of a numpy array. If not
            provided, generated from other arguments.

        modulation: Specifies the constellation (symbol set) in use by 
            each user. Symbols are assumed to be transmitted with equal probability.
            Options are:
               * 'BPSK'
                   Binary Phase Shift Keying. Transmitted symbols are +1, -1;
                   no encoding is required.
                   A real valued channel is assumed.

               * 'QPSK'
                   Quadrature Phase Shift Keying. 
                   Transmitted symbols are +1, -1, +1j, -1j;
                   spins are encoded as a real vector concatenated with an imaginary vector.
                   
               * '16QAM'
                   Each user is assumed to select independently from 16 symbols.
                   The transmitted symbol is a complex value that can be encoded by two spins
                   in the imaginary part, and two spins in the real part. v = 2 s_1 + s_2.
                   Highest precision real and imaginary spin vectors, are concatenated to 
                   lower precision spin vectors.
                   
               * '64QAM'
                   A QPSK symbol set is generated, symbols are further amplitude modulated 
                   by an independently and uniformly distributed random amount from [1, 3].

        num_transmitters: Number of users. Since each user transmits 1 symbol per frame, also the
             number of transmitted symbols, must be consistent with F argument.

        num_receivers: Num_Receivers of channel, :code:`len(y)`. Must be consistent with y argument.

        SNRb: Signal to noise ratio per bit on linear scale. When y is not provided, this is used
            to generate the noisy signal. In the case float('Inf') no noise is 
            added. SNRb = Eb/N0, where Eb is the energy per bit, and N0 is the one-sided
            power-spectral density. A one-sided . N0 is typically kB T at the receiver. 
            To convert units of dB to SNRb use SNRb=10**(SNRb[decibells]/10).
        
        transmitted_symbols: 
            The set of symbols transmitted, this argument is used in combination with F
            to generate the signal y.
            For BPSK and QPSK modulations the statistics
            of the ensemble are unimpacted by the choice (all choices are equivalent
            subject to spin-reversal transform). If the argument is None, symbols are
            chosen as 1 or 1 + 1j for all users, respectively for BPSK and QPSK.
            For QAM modulations, amplitude randomness impacts the likelihood in a 
            non-trivial way. If the argument is None in these cases, symbols are
            chosen i.i.d. from the appropriate constellation. Note that, for correct
            analysis of some solvers in BPSK and QPSK cases it is necessary to apply 
            a spin-reversal transform.

        F_distribution:
           When F is None, this argument describes the zero-mean variance 1 
           distribution used to sample each element in F. Permitted values are in
           tuple form: (str, str). The first string is either 
           'Normal' or 'Binary'. The second string is either 'Real' or 'Complex'.
           For large num_receivers and number of users the statistical properties of 
           the likelihood are weakly dependent on the first argument. Choosing 
           'Binary' allows for integer valued Hamiltonians, 'Normal' is a more 
           standard model. The channel can be Real or Complex. In many cases this 
           also represents a superficial distinction up to rescaling. For real 
           valued symbols (BPSK) the default is ('Normal', 'Real'), otherwise it
           is ('Normal', 'Complex')

        use_offset:
           When True, a constant is added to the Ising model energy so that
           the energy evaluated for the transmitted symbols is zero. At sufficiently
           high num_receivers/user ratio, and signal to noise ratio, this will
           be the ground state energy with high probability.

    Returns:
        The binary quadratic model defining the log-likelihood function

    Example:

        Generate an instance of a CDMA problem in the high-load regime, near a first order
        phase transition _[#T02, #R20]:

        >>> num_transmitters = 64
        >>> transmitters_per_receiver = 1.5
        >>> SNRb = 5
        >>> bqm = dimod.generators.spin_encoded_mimo(modulation='BPSK', num_transmitters = 64, \
                      num_receivers = round(num_transmitters/transmitters_per_receiver), \
                      SNRb=SNRb, \
                      F_distribution = ('Binary','Real'))

         
    .. [#T02] T. Tanaka IEEE TRANSACTIONS ON INFORMATION THEORY, VOL. 48, NO. 11, NOVEMBER 2002
    .. [#R20] J. Raymond, N. Ndiaye, G. Rayaprolu and A. D. King, "Improving performance of logical qubits by parameter tuning and topology compensation, " 2020 IEEE International Conference on Quantum Computing and Engineering (QCE), Denver, CO, USA, 2020, pp. 295-305, doi: 10.1109/QCE49297.2020.00044.
    .. [#Prince] Various (https://paws.princeton.edu/) 
    """
    
    if num_transmitters is None:
        if F is not None:
            num_transmitters = F.shape[1]
        elif transmitted_symbols is not None:
            num_transmitters = len(transmitted_symbols)
        else:
            raise ValueError('num_transmitters is not specified and cannot'
                                 'be inferred from F or transmitted_symbols (both None)')
    if num_receivers is None:
        if F is not None:
            num_receivers = F.shape[0]
        elif y is not None:
            num_receivers = y.shape[0]
        elif channel_noise is not None:
            num_receivers = channel_noise.shape[0]
        else:
            raise ValueError('num_receivers is not specified and cannot'
                             'be inferred from F, y or channel_noise (all None)')

    assert num_transmitters > 0, "Expect positive number of transmitters"
    assert num_receivers > 0, "Expect positive number of receivers"

    if F is None:
        seed = np.random.RandomState(seed)
        F, channel_power = create_channel(num_receivers=num_receivers, num_transmitters=num_transmitters,
                                          F_distribution=F_distribution, random_state=seed)
        #Channel power is the value relative to an assumed normalization E[Fui* Fui] = 1 
    else:
        channel_power = num_transmitters
       
    if y is None:
        y, _, _, _ = create_signal(F, transmitted_symbols=transmitted_symbols, channel_noise=channel_noise,
                                   SNRb=SNRb, modulation=modulation, channel_power=channel_power,
                                   random_state=seed)
    
    h, J, offset = _yF_to_hJ(y, F, modulation)
  
    if use_offset:
        return dimod.BQM(h[:,0], J, 'SPIN', offset=offset)
    else:
        np.fill_diagonal(J, 0)
        return dimod.BQM(h[:,0], J, 'SPIN')

def _make_honeycomb(L: int):
    """ 2L by 2L triangular lattice with open boundaries,
    and cut corners to make hexagon. """
    G = nx.Graph()
    G.add_edges_from([((x, y), (x,y+ 1)) for x in range(2*L+1) for y in range(2*L)])
    G.add_edges_from([((x, y), (x+1, y)) for x in range(2*L) for y in range(2*L + 1)])
    G.add_edges_from([((x, y), (x+1, y+1)) for x in range(2*L) for y in range(2*L)])
    G.remove_nodes_from([(i,j) for j in range(L) for i in range(L+1+j,2*L+1) ])
    G.remove_nodes_from([(i,j) for i in range(L) for j in range(L+1+i,2*L+1)])
    return G

def spin_encoded_comp(lattice: Union[int,nx.Graph],
                      modulation: str, ys: Union[np.array, None] = None,
                      Fs: Union[np.array, None] = None,
                      *,
                      transmitted_symbols: Union[np.array, None] = None, channel_noise: Union[np.array, None] = None, 
                      num_transmitters: int = None,  num_receivers: int = None, SNRb: float = float('Inf'), 
                      seed: Union[None, int, np.random.RandomState] = None, 
                      F_distribution: Union[None, str] = None, 
                      use_offset: bool = False) -> dimod.BinaryQuadraticModel:
    """Defines a simple coooperative multi-point decoding problem coMD.
    Args:
       lattice: A graph defining the set of nearest neighbor basestations. Each 
           basestation has ``num_receivers`` receivers and ``num_transmitters`` 
           local transmitters. Transmitters from neighboring basestations are also 
           received. The channel F should be set to None, it is not dependent on the
           geometric information for now.
           lattice can also be set to an integer value, in which case a honeycomb 
           lattice of the given linear scale (number of basestations O(L^2)) is 
           created using ``_make_honeycomb()``.
       Fs: A dictionary of channels, one per basestation.
       ys: A dictionary of signals, one per basestation.
     
       See for ``spin_encoded_mimo`` for interpretation of other per-basestation parameters. 
    Returns:
       bqm: an Ising model in BinaryQuadraticModel format.
    
    Reference: 
        https://en.wikipedia.org/wiki/Cooperative_MIMO
    """
    if type(lattice) is not nx.Graph:
        lattice = _make_honeycomb(int(lattice))
    if num_transmitters == None:
        num_transmitters = 1
    if num_receivers == None:
        num_receivers = 1
    if ys is None:
        ys = {bs : None for bs in lattice.nodes()}
    if Fs is None:
        Fs = {bs : None for bs in lattice.nodes()}
    if (modulation != 'BPSK' and modulation != 'QPSK') or transmitted_symbols is not None:
        raise ValueError('Generation of problems for which transmitted symbols are'
                         'not all 1 (default BPSK,QPSK) not yet supported.')
    if SNRb < float('Inf'):
        #Spread across basestations by construction
        SNRb /= (1 + 2*lattice.num_edges/lattice.num_nodes)
    #Convert graph labels
    bqm = dimod.BinaryQuadraticModel('SPIN');
    for bs in lattice.nodes():
        bqm_cell = spin_encoded_mimo(
            modulation, ys[bs], Fs[bs],
            transmitted_symbols=transmitted_symbols, channel_noise=channel_noise,
            num_transmitters=num_transmitters*(1 + lattice.degree(bs)),
            num_receivers=num_receivers, SNRb=SNRb, seed=seed,
            F_distribution=F_distribution, use_offset=use_offset)
        geometric_labels = [(bs,i) for i in range(num_transmitters)] +\
                           [(neigh,i) for neigh in lattice.neighbors(bs)
                            for i in range(num_transmitters)]
        bqm_cell.relabel_variables({idx : l for idx,l in
                                    enumerate(geometric_labels)})
        bqm = bqm + bqm_cell;

    return bqm
