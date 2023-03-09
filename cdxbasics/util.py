"""
Basic utilities for Python
Hans Buehler 2022
"""

import datetime as datetime
import types as types
from functools import wraps
import hashlib as hashlib
import inspect as inspect
from collections.abc import Mapping, Collection
from .prettydict import PrettyDict

# support for numpy and pandas is optional for this module
# At the moment both are listed as dependencies in setup.py to ensure
# they are tested in github
np = None
pd = None

try:
    import numpy as np
except:
    pass
try:
    import pandas as pd
except:
    pass

# =============================================================================
# basic indentification short cuts
# =============================================================================

__types_functions = None

def types_functions():
    """ Returns all types.* considered function """
    global __types_functions
    if __types_functions is None:
        __types_functions = set()
        try: __types_functions.add(types.FunctionType)
        except: pass
        try: __types_functions.add(types.LambdaType)
        except: pass
        try: __types_functions.add(types.CodeType)
        except: pass
        #types.MappingProxyType
        #types.SimpleNamespace
        try: __types_functions.add(types.GeneratorType)
        except: pass
        try: __types_functions.add(types.CoroutineType)
        except: pass
        try: __types_functions.add(types.AsyncGeneratorType)
        except: pass
        try: __types_functions.add(types.MethodType)
        except: pass
        try: __types_functions.add(types.BuiltinFunctionType)
        except: pass
        try: __types_functions.add(types.BuiltinMethodType)
        except: pass
        try: __types_functions.add(types.WrapperDescriptorType)
        except: pass
        try: __types_functions.add(types.MethodWrapperType)
        except: pass
        try: __types_functions.add(types.MethodDescriptorType)
        except: pass
        try: __types_functions.add(types.ClassMethodDescriptorType)
        except: pass
        #types.ModuleType,
        #types.TracebackType,
        #types.FrameType,
        try: __types_functions.add(types.GetSetDescriptorType)
        except: pass
        try: __types_functions.add(types.MemberDescriptorType)
        except: pass
        try: __types_functions.add(types.DynamicClassAttribute)
        except: pass
        __types_functions = tuple(__types_functions)
    return __types_functions

def isFunction(f) -> bool:
    """ Checks whether 'f' is a function in an extended sense. Check 'types_functions' for what is tested against"""
    return isinstance(f,types_functions())

def isAtomic( o ):
    """ Returns true if 'o' is a string, int, float, date or bool """
    if type(o) in [str,int,bool,float,datetime.date]:
        return True
    if not np is None and isinstance(o,np.generic):
        return True
    return False

def isFloat( o ):
    """ Checks whether a type is a float """
    if type(o) is float:
        return True
    if not np is None and isinstance(o,np.floating):
        return True
    return False

# =============================================================================
# string formatting
# =============================================================================

def _fmt( text : str, args = None, kwargs = None ) -> str:
    """ Utility function. See fmt() """
    if text.find('%') == -1:
        return text
    if not args is None and len(args) > 0:
        assert kwargs is None or len(kwargs) == 0, "Cannot specify both 'args' and 'kwargs'"
        return text % tuple(args)
    if not kwargs is None and len(kwargs) > 0:
        return text % kwargs
    return text

def fmt(text : str,*args,**kwargs) -> str:
    """
    String formatting made easy
        text - pattern
    Examples
        fmt("The is one = %ld", 1)
        fmt("The is text = %s", 1.3)
        fmt("Using keywords: one=%(one)d, two=%(two)d", two=2, one=1)
    """
    return _fmt(text,args,kwargs)

def prnt(text : str,*args,**kwargs) -> str:
    """ Prints a fmt() string. """
    print(_fmt(text,args,kwargs))
def write(text : str,*args,**kwargs) -> str:
    """ Prints a fmt() string without EOL, e.g. uses print(fmt(..),end='') """
    print(_fmt(text,args,kwargs),end='')

# =============================================================================
# Conversion of arbitrary python elements into re-usable versions
# =============================================================================

def plain( inn, sorted = False ):
    """
    Converts a python structure into a simple atomic/list/dictionary collection such
    that it can be read without the specific imports used inside this program.
    or example, objects are converted into dictionaries of their data fields.
    
    Hans Buehler, Dec 2013
    """
    # basics
    if isAtomic(inn) \
        or isinstance(inn,(datetime.time,datetime.date,datetime.datetime))\
        or (False if np is None else isinstance(inn,np.ndarray)) \
        or inn is None:
        return inn
    # can't handle functions --> return None
    if isFunction(inn) or isinstance(inn,property):
        return None
    # dictionaries
    if isinstance(inn,dict):
        out = {}
        for k in inn:
            out[k] = plain(inn[k])
        return out
    # pandas
    if not pd is None and isinstance(inn,pd.DataFrame):
        plain(inn.columns)
        plain(inn.index)
        plain(inn.to_numpy())
        return
    # lists, tuples and everything which looks like it --> lists
    if not getattr(inn,"__iter__",None) is None: #isinstance(inn,list) or isinstance(inn,tuple):
        return [ plain(k) for k in inn ]
    # handle objects as dictionaries, removing all functions
    if not getattr(inn,"__dict__",None) is None:
        out = {}
        for k in inn.__dict__:
            x = inn.__dict__[k]
            if not isFunction(x):
                out[k] = plain(x)
        return out
    # nothing we can do
    raise TypeError(fmt("Cannot handle type %s", type(inn)))

# =============================================================================
# Hashing / unique representatives
# =============================================================================

def _compress_function_code( f ):
    """ Returns a compressed version of the code of the function 'f' """
    src = inspect.getsourcelines( f )[0]
    if isinstance(f,types.LambdaType):
        assert len(src) > 0, "No source code ??"
        l = src[0]
        i = l.lower().find("lambda ")
        src[0] = l[i+len("lambda "):]        
    src = [ l.replace("\t"," ").replace(" ","").replace("\n","") for l in src ]
    return src

def uniqueHashExt( length, parse_functions = False ):
    """ Returns a function which generates hashes of length 'length', or of standard length if length is None """
    def unique_hash(*args, **kwargs) -> str:
        """ 
        Generates a hash key for any collection of python objects.
        Typical use is for key'ing data vs a unique configuation.
        
        The function
            1) uses the repr() function to feed objects to the hash algorithm.
               that means is only distinguishes floats up to str conversion precision
            2) keys of dictionaries, and sets are sorted to ensure equality of hashes
               accross different memory setups of strings
            3) Members with leading '_' are ignored
            4) Functions and properties are ignored
        
        Hans Buehler 2017
        """    
        m = hashlib.md5() if length is None else hashlib.shake_128()
        def update(s):
            s_ =  repr(s).encode('utf-8')
            m.update(s_)
        def visit(inn):
            # basics
            if inn is None:
                return
            # by default do not handle functions.
            if isFunction(inn) or isinstance(inn,property):
                if parse_functions: update( _compress_function_code(inn) )
                return 
            # basic elements
            if isAtomic(inn):
                update(inn)
                return
            # some standard types
            if isinstance(inn,(datetime.time,datetime.date,datetime.datetime)):
                update(inn)
                return
            # numpy
            if not np is None and isinstance(inn,np.ndarray):
                update(inn)
                return
            # pandas
            if not pd is None and isinstance(inn,pd.DataFrame):
                update(inn)
                return
            # dictionaries, and similar
            if isinstance(inn,Mapping):
                assert not isinstance(inn, list)
                inn_ = sorted(inn.keys())
                for k in inn_:
                    if k[:1] == '_':
                        continue
                    update(k)
                    visit(inn[k])
                return
            # lists, tuples and everything which looks like it --> lists
            if isinstance(inn, Collection):
                assert not isinstance(inn, dict)
                for k in inn:
                    if isinstance(k,str) and k[:1] == "_":
                        continue
                    visit(k)
                return
            # objects: treat like dictionaries        
            inn_ = getattr(inn,"__dict__",None)
            if inn_ is None:
                raise TypeError(fmt("Cannot handle type %s", type(inn)))        
            assert isinstance(inn_,Mapping)
            visit(inn_)
            
        visit(args)
        visit(kwargs)
        return m.hexdigest() if length is None else m.hexdigest(length//2)
    unique_hash.name = "uniqueHash(%s,%s)" % (str(length),str(parse_functions))
    return unique_hash

def uniqueHash(*args, **kwargs) -> str:
    """ 
    Generates a hash key for any collection of python objects.
    Typical use is for key'ing data vs a unique configuation.
    
    The function
        1) uses the repr() function to feed objects to the hash algorithm.
           that means is only distinguishes floats up to str conversion precision
        2) keys of dictionaries, and sets are sorted to ensure equality of hashes
           accross different memory setups of strings
        3) Members with leading '_' are ignored
        4) Functions and properties are ignored
    
    Hans Buehler 2017
    """    
    return uniqueHashExt(None)(*args,**kwargs)

def uniqueHash32( *args, **argv ) -> str:
    """ Compute a unique ID of length 32 for the provided arguments """
    return uniqueHashExt(32)(*args,**argv)

def uniqueHash48( *args, **argv ) -> str:
    """ Compute a unique ID of length 48 for the provided arguments """
    return uniqueHashExt(48)(*args,**argv)

def uniqueHash64( *args, **argv ) -> str:
    """ Compute a unique ID of length 64 for the provided arguments """
    return uniqueHashExt(64)(*args,**argv)

# =============================================================================
# Caching tools
# =============================================================================

class CacheMode(object):
    """
    CacheMode
    A class which encodes standard behaviour of a caching strategy:
    
                                                on    gen    off     update   clear   readonly
        load upon start from disk if exists     x     x     -       -        -       x
        write updates to disk                   x     x     -       x        -       -
        delete existing object upon start       -     -     -       -        x       -
        delete existing object if incompatible  x     -     -       x        x       -
        
    See cdxbasics.subdir for functions to manage files.
    """
    
    ON = "on"
    GEN = "gen"
    OFF = "off"
    UPDATE = "update"
    CLEAR = "clear"
    READONLY = "readonly"
    
    MODES = [ ON, GEN, OFF, UPDATE, CLEAR, READONLY ]
    HELP = "'on' for standard caching; 'gen' for caching but keep existing incompatible files; 'off' to turn off; 'update' to overwrite any existing cache; 'clear' to clear existing caches; 'readonly' to read existing caches but not write new ones"
    
    def __init__(self, mode : str = None ):
        """
        Encodes standard behaviour of a caching strategy:

                                                    on    gen    off     update   clear   readonly
            load upon start from disk if exists     x     x     -       -        -       x
            write updates to disk                   x     x     -       x        -       -
            delete existing object upon start       -     -     -       -        x       -
            delete existing object if incompatible  x     -     -       x        x       -
            
        Parameters
        ----------
            mode : str
                Which mode to use.
        """
        mode      = self.ON if mode is None else mode
        self.mode = mode.mode if isinstance(mode, CacheMode) else str(mode)
        if not self.mode in self.MODES:
            raise KeyError( self.mode, "Caching mode must be 'on', 'off', 'update', 'clear', or 'readonly'. Found " + self.mode )
        self._read   = self.mode in [self.ON, self.READONLY, self.GEN]
        self._write  = self.mode in [self.ON, self.UPDATE, self.GEN]
        self._delete = self.mode in [self.UPDATE, self.CLEAR]
        self._del_in = self.mode in [self.UPDATE, self.CLEAR, self.ON]
        
    @property
    def read(self) -> bool:
        """ Whether to load any existing data when starting """
        return self._read
    
    @property
    def write(self) -> bool:
        """ Whether to write cache data to disk """
        return self._write
    
    @property
    def delete(self) -> bool:
        """ Whether to delete existing data """
        return self._delete
    
    @property
    def del_incomp(self) -> bool:
        """ Whether to delete existing data if it is not compatible """
        return self._del_in
    
    def __str__(self) -> str:# NOQA
        return self.mode
    def __repr__(self) -> str:# NOQA
        return self.mode
        
    def __eq__(self, other) -> bool:# NOQA
        return self.mode == other
    def __neq__(self, other) -> bool:# NOQA
        return self.mode != other
    
    @property
    def is_off(self) -> bool:
        """ Whether this cache mode is OFF """
        return self.mode == self.OFF

    @property
    def is_on(self) -> bool:
        """ Whether this cache mode is ON """
        return self.mode == self.ON

    @property
    def is_gen(self) -> bool:
        """ Whether this cache mode is GEN """
        return self.mode == self.GEN

    @property
    def is_update(self) -> bool:
        """ Whether this cache mode is UPDATE """
        return self.mode == self.UPDATE

    @property
    def is_clear(self) -> bool:
        """ Whether this cache mode is CLEAR """
        return self.mode == self.CLEAR

    @property
    def is_readonly(self) -> bool:
        """ Whether this cache mode is READONLY """
        return self.mode == self.READONLY

# =============================================================================
# functional programming
# =============================================================================

def bind( F, **kwargs ):
    """ 
    Binds default named arguments to F.
    For example
        def F(x,y):
            return x*y
        Fx = bind(F,y=2.)
        Fx(1.)             # x=1
        Fx(1.,2.)          # x=1, y=2
        Fx(1.,y=3.)        # x=1, y=3
    """
    kwargs_ = dict(kwargs)
    @wraps(F)
    def binder( *liveargs, **livekwargs ):
        k = dict(livekwargs)
        k.update(kwargs_)
        return F(*liveargs,**k)
    return binder

# =============================================================================
# generic class
# (superseded)
# =============================================================================

Generic = PrettyDict

# =============================================================================
# Some formatting
# =============================================================================

def fmt_seconds( seconds : int ) -> str:
    """ Print nice format string for seconds """
    if seconds < 60:
        return "%lds" % seconds
    if seconds < 60*60:
        return "%ld:%02ld" % (seconds//60, seconds%60)
    return "%ld:%02ld:%02ld" % (seconds//60//60, (seconds//60)%60, seconds%60)    

def fmt_list( lst, none="-" ) -> str:
    """ Returns a nicely formatted list of string with commas """
    if lst is None:
        return none
    if len(lst) == 0:
        return none
    if len(lst) == 1:
        return str(lst[0])
    if len(lst) == 2:
        return str(lst[0]) + " and " + str(lst[1])
    s = ""
    for k in lst[:-1]:
        s += str(k) + ", "
    return s[:-2] + " and " + str(lst[-1])
    
def fmt_big_number( number : int ) -> str:
    """ Return a nicely formatted big number string """
    if number >= 10**10:
        number = number//(10**9)
        number = round(number,2)
        return "%gG" % number
    if number >= 10**7:
        number = number//(10**6)
        number = round(number,2)
        return "%gM" % number
    if number >= 10**4:
        number = number/(10**3)
        number = round(number,2)
        return "%gK" % number
    return str(number)

def fmt_datetime(dt : datetime.datetime) -> str:
    """ Returns string for 'dt' """
    if isinstance(dt, datetime.datetime):
        return "%04ld-%02ld-%02ld %02ld:%02ld:%02ld" % ( dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second )
    if isinstance(dt, datetime.date):
        return "%04ld-%02ld-%02ld" % ( dt.year, dt.month, dt.day )
    assert isinstance(dt, datetime.time), "'dt' must be datetime, date, or time. Found %s" % type(dt)
    return "%02ld:%02ld:%02ld" % ( dt.hour, dt.minute, dt.second )

def fmt_now() -> str:
    """ Returns string for 'now' """
    return fmt_datetime(datetime.datetime.now())
