#!/usr/bin/env python
# -*- coding: utf-8 -*-


import errno
import logging
import os

from exceptions import RuntimeError

import docopt
import dotmap


logger = logging.getLogger(__name__)


def docopt_plus(doc_string, version_message):
    '''docopt.docopt() returns a dict object.  This converts it to a DotMap
    object, which allows access to keys via a 'dot' notation (i.e., like that
    of namedtuple, except that values can be changed).

    '''

    args = docopt.docopt(doc_string, version=version_message)
    # remove any dashes or double dashes preceding option names
    args = {k.replace('-', '') : args[k] for k in args.keys()}
    args = dotmap.DotMap(args)
    return args


def makedirs(path, exists_ok=False):
    # Behave similarly to Python 3.2+ os.makedirs()
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exists_ok and exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise
    return path



#;;; Local Variables:
#;;; mode: python
#;;; coding: utf-8
#;;; eval: (auto-fill-mode)
#;;; eval: (set-fill-column 78)
#;;; eval: (fci-mode)
#;;; End:
