''' Test cases for uncertainty core. '''
import pytest

import os
import numpy as np
import sympy

import psluncert as uc
from psluncert import uncertainty
from psluncert import curvefit


def test_chain():
    ''' Test chaining of functions '''
    u = uc.UncertaintyCalc(seed=0)
    varid = id(u.variables)  # Make sure this doesn't change!
    u.set_input('x', nom=100, std=1)  # Test adding uncertainties via set_input()
    u.set_input('y', nom=50, std=1)
    u.set_function('x+y', name='f')
    u.set_function('2*f', name='g')
    u.set_function('2*g', name='h')
    u.calculate()
    assert np.isclose(u.out.f.gum.mean, u.out.g.gum.mean/2)
    assert np.isclose(u.out.g.gum.mean, u.out.h.gum.mean/2)
    assert np.isclose(u.out.f.gum.uncert, u.out.g.gum.uncert/2)
    assert np.isclose(u.out.g.gum.uncert, u.out.h.gum.uncert/2)

    assert np.isclose(u.out.f.mc.mean, u.out.g.mc.mean/2, rtol=.02)
    assert np.isclose(u.out.g.mc.mean, u.out.h.mc.mean/2, rtol=.02)
    assert np.isclose(u.out.f.mc.uncert, u.out.g.mc.uncert/2, rtol=.05)
    assert np.isclose(u.out.g.mc.uncert, u.out.h.mc.uncert/2, rtol=.05)

    # Now change the base equation and verify everything trickles down
    oldh_mean = u.out.h.gum.mean
    oldh_unc = u.out.h.gum.uncert
    u.set_function('(x+y)/2', name='f')
    u.calculate()
    assert oldh_mean/2 == u.out.h.gum.mean
    assert oldh_unc/2 == u.out.h.gum.uncert

    assert np.isclose(u.out.f.gum.mean, u.out.g.gum.mean/2)
    assert np.isclose(u.out.g.gum.mean, u.out.h.gum.mean/2)
    assert np.isclose(u.out.f.gum.uncert, u.out.g.gum.uncert/2)
    assert np.isclose(u.out.g.gum.uncert, u.out.h.gum.uncert/2)

    assert np.isclose(u.out.f.mc.mean, u.out.g.mc.mean/2, rtol=.02)
    assert np.isclose(u.out.g.mc.mean, u.out.h.mc.mean/2, rtol=.02)
    assert np.isclose(u.out.f.mc.uncert, u.out.g.mc.uncert/2, rtol=.02)
    assert np.isclose(u.out.g.mc.uncert, u.out.h.mc.uncert/2, rtol=.02)
    assert id(u.variables) == varid

    # Double-chaining, order shouldn't matter
    u2 = uc.UncertaintyCalc(['g = a*b*f', 'f = a+b*c+h', 'h=a+d'])
    u2.set_input('a', nom=10, std=1)
    u2.set_input('b', nom=10, std=1)
    u2.set_input('c', nom=1, std=.5)
    u2.set_input('d', nom=1, std=.5)
    u2.calculate()
    u2.out.report_sens()  # This was crashing before
    symbols = u2.functions[0].get_basefunc()
    symbols = [str(s) for s in u2.functions[0].get_basefunc().free_symbols]
    assert 'a' in symbols
    assert 'b' in symbols
    assert 'c' in symbols
    assert 'd' in symbols
    assert 'f' not in symbols  # Functions were substituted out
    assert 'g' not in symbols
    assert 'h' not in symbols


def test_callable():
    ''' Test callable (named arguments) and vectorizable function as input '''
    def myfunc(a, b):
        return a + b**2

    u = uc.UncertaintyCalc(myfunc, seed=0)
    reqinpts = u.get_reqd_inputs()
    assert 'a' in reqinpts
    assert 'b' in reqinpts
    assert len(reqinpts) == 2
    u.add_required_inputs()
    assert len(u.variables) == 3  # a, b, myfunc
    assert 'a' in u.functions[0].get_basenames()
    assert 'b' in u.functions[0].get_basenames()

    u.set_input('a', nom=5)
    u.set_input('b', nom=2)
    u.set_uncert('a', std=.05)
    u.set_uncert('b', std=.02)
    assert u.functions[0].get_basemeans()['a'] == 5

    u.calculate()
    assert np.isclose(u.out.get_output(method='gum').mean, 9)


def test_callablekwargs():
    ''' Test callable with **kwargs '''
    def myfunc(**kwargs):
        x = kwargs.get('x')
        y = kwargs.get('y')
        return x * y

    with pytest.raises(ValueError):  # Error if function takes unnamed kwargs and kwnames parameter not specified
        u = uc.UncertaintyCalc(myfunc, seed=0)

    u = uc.UncertaintyCalc(seed=0)
    u.set_function(myfunc, kwnames=['x', 'y'])
    reqinpts = u.get_reqd_inputs()
    assert 'x' in reqinpts
    assert 'y' in reqinpts
    assert len(reqinpts) == 2

    u.set_input('x', nom=2)
    u.set_input('y', nom=4)
    u.set_uncert('x', std=.1)
    u.set_uncert('y', std=.2)
    u.calculate()
    assert np.isclose(u.out.get_output(method='gum').mean, 8)


def test_chaincallable():
    ''' Test chaining callable functions '''
    def myfunc1(x, y):
        return x * y

    def myfunc2(myfunc1):
        return myfunc1 + 100

    u = uc.UncertaintyCalc(seed=0)
    u.set_function(myfunc1)
    u.set_function(myfunc2)
    reqinpts = u.get_reqd_inputs()
    assert 'x' in reqinpts
    assert 'y' in reqinpts
    u.add_required_inputs()
    assert 'x' in u.functions[0].get_basenames()
    assert 'y' in u.functions[0].get_basenames()
    assert len(u.functions[0].get_basenames()) == 2
    assert 'myfunc1' in u.functions[1].get_basenames()
    assert len(u.functions[1].get_basenames()) == 1

    u.set_input('x', nom=2)
    u.set_input('y', nom=10)
    u.set_uncert('x', std=.1)
    u.set_uncert('y', std=.5)
    u.calcGUM()
    assert np.isclose(u.out.get_output(fidx=0, method='gum').mean, 20)
    assert np.isclose(u.out.get_output(fidx=1, method='gum').mean, 120)

    cont = u.get_contour(0,1)  # Test contour generation - when functions have different length arguments
    assert cont[0].shape == (50,50)  # X grid
    assert cont[1].shape == (50,50)  # Y grid
    assert cont[2].shape == (50,50)  # PDF grid


def test_vectorize():
    ''' Make sure non-vectorized functions can run. Also tests function with kwargs arguments '''
    # This function is not vectorizable as-is. Calculator will try it, fail, and then
    # try using np.vectorize() on it.
    def tcr(**kwargs):
        ''' Temperature Coefficient of Resistance from pairs of R, T measurements. '''
        R = np.array([kwargs.get('R{}'.format(i+1)) for i in range(len(kwargs)//2)])
        T = np.array([kwargs.get('T{}'.format(i+1)) for i in range(len(kwargs)//2)])
        p = np.polyfit(T-T[0], R/R[0]-1, deg=1)[0]
        return p

    varnames = ['T{}'.format(i+1) for i in range(4)] + ['R{}'.format(i+1) for i in range(4)]

    u = uc.UncertaintyCalc(samples=1000)
    u.set_function(tcr, kwnames=varnames)
    for i, rval in enumerate([100, 100.1, 100.2, 100.3]):
        Rname = 'R{}'.format(i+1)
        u.set_input(Rname, nom=rval)
        u.set_uncert(Rname, std=.2)
    for i, tval in enumerate([20, 22, 24, 26]):
        Tname = 'T{}'.format(i+1)
        u.set_input(Tname, nom=tval)
        u.set_uncert(Tname, std=.05)
    u.calculate(GUM=False)
    MC = u.out.get_output(method='mc')
    assert np.isclose(MC.mean, 0.0005, atol=.0001)


@pytest.mark.filterwarnings('ignore')  # Will generate a np warning about degrees of freedom <= 0
def test_constant():
    ''' Functions can also be constant with no variables. '''
    u = uc.UncertaintyCalc()
    u.set_function('10', name='a')
    u.set_function('a+b')
    u.set_input('b', 5)
    u.set_uncert('b', std=0.1)
    u.calculate()
    GUM1 = u.out.a.gum
    GUM2 = u.out.get_output(fidx=1, method='gum')
    assert np.isclose(GUM1.mean, 10)
    assert np.isclose(GUM2.mean, 15)


def test_readconfig():
    ''' Test read_configfile '''
    u = uc.UncertaintyCalc.from_configfile(os.path.join('test', 'test1.yaml'))
    assert [f.origfunction for f in u.functions] == ['f = (a + b) / c', 'g = a - b', 'h = b * c']
    assert u.samples == 1E6
    assert len(u.get_baseinputs()) == 3
    a = u.get_input('a')
    assert a.name == 'a'
    assert a.nom == 10.0
    assert a.uncerts[0].args['std'] == 0.2
    assert a.uncerts[0].distname == 'normal'
    assert a.degf() == 10
    b = u.get_input('b')
    assert b.name == 'b'
    assert b.nom == 25.0
    assert b.uncerts[0].args['scale'] == 2.0
    assert b.uncerts[0].args['a'] == 5.0
    assert b.uncerts[0].distname == 'gamma'
    assert b.degf() == np.inf
    c = u.get_input('c')
    assert c.name == 'c'
    assert c.nom == 2.0
    assert c.uncerts[0].args['std'] == 0.1
    assert c.uncerts[0].distname == 'normal'
    assert c.degf() == 88
    corlist = u.get_corr_list()
    assert ('b', 'a', -0.36) in corlist or ('a', 'b', -0.36) in corlist
    assert ('a', 'c', -0.4) in corlist or ('c', 'a', -0.4) in corlist
    assert ('b', 'c', 0.86) in corlist or ('c', 'b', 0.86) in corlist

def test_saveconfig():
    ''' Test save_config and read_config, we can go in a circle. '''
    CHECK_FILE = os.path.join('test', 'TEST_SAVE.YAML')

    u = uc.UncertaintyCalc.from_configfile(os.path.join('test', 'test1.yaml'))
    u.save_config(CHECK_FILE)
    u2 = uc.UncertaintyCalc.from_configfile(CHECK_FILE)

    assert [str(f) for f in u.functions] == [str(f) for f in u2.functions]
    assert u.variables[0].name == u2.variables[0].name
    assert u.variables[1].name == u2.variables[1].name
    assert u.variables[2].name == u2.variables[2].name
    assert np.allclose(u._corr, u2._corr, rtol=1E-9, atol=0)
    assert u.samples == u2.samples
    os.remove(CHECK_FILE)

def test_addinputs():
    ''' Test add_required_inputs() function '''
    # For a string function...
    u = uc.UncertaintyCalc('a + b + c + d')
    u.set_input('a', nom=1)
    u.add_required_inputs()

    assert len(u.get_baseinputs()) == 4
    names = [i.name for i in u.variables]
    assert 'b' in names
    assert 'c' in names
    assert 'd' in names

    # and a sympy function...
    x,y,z = sympy.symbols('x y z')
    f = x+y+z
    u = uc.UncertaintyCalc(f)
    u.add_required_inputs()
    assert len(u.get_baseinputs()) == 3
    names = [i.name for i in u.variables]
    assert 'x' in names
    assert 'y' in names
    assert 'z' in names

    # and for callable...
    def myfunc(j,k,l):
        return j+k+l
    u = uc.UncertaintyCalc(myfunc)
    u.add_required_inputs()
    assert len(u.get_baseinputs()) == 3
    names = [i.name for i in u.variables]
    assert 'j' in names
    assert 'k' in names
    assert 'l' in names

def test_checkinput():
    ''' Test InputVar.check_args '''
    i = uc.InputUncert('b', nom=10, dist='gamma', std=1)
    assert i.check_args() == True # 'a' parameter automatically set to 1
    assert 'a' in i.args

    i = uc.InputUncert('b', nom=10, dist='gamma', std=1, a=-1)
    assert i.check_args() == False # Invalid 'a' parameter value

    # ValueError if not all inputs are defined
    u = uc.UncertaintyCalc('a+b')
    with pytest.raises(ValueError):
        u.calculate(MC=False)

def test_reqargs():
    ''' Test InputVar.req_args() '''
    args = uc.InputUncert('b', dist='gamma').required_args
    assert 'a' in args

    args = uc.InputUncert('b', dist='t').required_args
    assert 'df' in args

    args = uc.InputUncert('b', dist='burr').required_args
    assert 'c' in args
    assert 'd' in args

@pytest.mark.filterwarnings('ignore')  # Will generate a np warning about degrees of freedom <= 0
def test_reserved():
    ''' Test that reserved sympy keywords/functions are properly handled. '''
    # "pi" is 3.14, not a symbol
    u = uc.UncertaintyCalc('pi', seed=0)
    u.calculate(MC=False)
    assert np.isclose(u.out.get_output(method='gum').mean, np.pi)

    # "gamma" is a symbol, not gamma function
    u = uc.UncertaintyCalc('gamma/2')
    u.set_input('gamma', nom=10)
    u.calculate(MC=False)
    assert np.isclose(u.out.get_output(method='gum').mean, 5)

    # But '"cos" is the sympy cosine, not a variable
    u = uc.UncertaintyCalc('cos(x)')
    u.set_input('x', nom=np.pi)
    u.calculate(MC=False)
    assert np.isclose(u.out.get_output(method='gum').mean, np.cos(np.pi))

def test_reorder():
    ''' Test UncertCalc.reorder() '''
    u = uc.UncertaintyCalc(['f=a+b', 'g=a*b'])
    assert u.get_functionnames() == ['f', 'g']
    u.reorder(['g','f'])
    assert u.get_functionnames() == ['g', 'f']

def test_seed():
    ''' Test random seed argument '''
    # With seed, outputs will be the same
    u = uc.UncertaintyCalc('f=a+b', seed=10)
    u.set_input('a', nom=10)
    u.set_input('b', nom=5)
    u.set_uncert('a', std=.1)
    u.set_uncert('b', std=.05)
    u.calculate()
    vals = u.out.f.mc.samples[:10]  # Check first 10 samples
    u.calculate()
    assert (u.out.f.mc.samples[:10] == vals).all()

    # With seed=None, seed is randomized
    u = uc.UncertaintyCalc('f=a+b', seed=None)
    u.set_input('a', nom=10)
    u.set_input('b', nom=5)
    u.set_uncert('a', std=.1)
    u.set_uncert('b', std=.05)
    u.calculate()
    vals = u.out.f.mc.samples[:10]  # Check first 10 samples
    u.calculate()
    assert not (u.out.f.mc.samples[:10] == vals).all()

def test_change():
    ''' Test changing function name to an existing variable. Bug found in 0.09.

        setfunction -> R = V/I
        add_required_inputs
        setfunction -> V = IR
        add_required_inputs
        ==> R is now InputVar and V is InputFunc
    '''
    u = uc.UncertaintyCalc('R = V/I')
    u.add_required_inputs()
    names = [i.name for i in u.variables]
    assert 'R' in names
    assert 'V' in names
    assert 'I' in names
    assert isinstance(u.get_input('R'), uncertainty.InputFunc)
    assert isinstance(u.get_input('V'), uncertainty.InputVar)
    assert isinstance(u.get_input('I'), uncertainty.InputVar)

    u.set_function('I*R', idx=0, name='V')
    u.add_required_inputs()
    assert 'R' in names
    assert 'V' in names
    assert 'I' in names
    assert isinstance(u.get_input('R'), uncertainty.InputVar)
    assert isinstance(u.get_input('V'), uncertainty.InputFunc)
    assert isinstance(u.get_input('I'), uncertainty.InputVar)

def test_expanded():
    ''' Test expanded uncertainty of MC using shortest and symmetric intervals.
        Results should be similar for symmetric distributions
    '''
    np.random.seed(12345)
    x = np.linspace(0, 10, num=10)
    uy = .5
    y = 2*x + np.random.normal(loc=0, scale=uy, size=len(x))
    arr = curvefit.Array(x, y, uy=uy)
    fit = curvefit.CurveFit(arr)
    fit.calculate(mc=True)
    mins, maxs, ks = fit.out.mc.expanded()
    mins2, maxs2, ks2 = fit.out.mc.expanded(shortest=True)
    assert np.allclose(mins, mins2, atol=.1)
    assert np.allclose(maxs, maxs2, atol=.1)
    assert np.allclose(ks, ks2, atol=.1)


