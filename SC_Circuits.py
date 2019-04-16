import numpy as np
import cma

import SC_Utils as util

class QuantumStep:
    def __init__(self):
        raise NotImplementedError("Subclasses of QuantumStep should declare their own initializers.")
        # NOTE: QuantumStep initializers must set self._num_inputs
    
    def matrix(self, v):
        raise NotImplementedError("Subclasses of QuantumStep are required to implement the matrix(v) method.")

    def path(self, v):
        raise NotImplementedError("Subclasses of QuantumStep are required to implement the path(v) method.")

    def assemble(self, v, i=0):
        raise NotImplementedError("Subclasses of QuantumStep are required to implement the assemble(v, i) method.")

    def copy(self):
        return self

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __repr__(self):
        return "QuantumStep()"


class IdentityStep:  
    def __init__(self, n=2, dits=1):
        self._num_inputs=0
        self._I = np.matrix(np.eye(n), dtype='complex128')
        self._dits = dits
        self._n = n

    def matrix(self, v):
        return self._I

    def path(self, v):
        return ["IDENTITY"]

    def assemble(self, v, i=0):
        return ""

    def __repr__(self):
        return "IdentityStep({})".format(self._n)
    


class SingleQubitStep(QuantumStep):
    def __init__(self):
        self._num_inputs = 3
        self._dits = 1

        self._x90 = util.rot_x(np.pi/2)
        self._rot_z = util.rot_z(0)
        self._out = np.matrix(np.eye(2), dtype='complex128')
        
    def matrix(self, v):
        util.re_rot_z(v[0], self._rot_z)
        self._out = np.dot(self._rot_z, self._x90, out=self._out)
        util.re_rot_z(v[1] + np.pi, self._rot_z)
        self._out = np.dot(self._out, self._rot_z, out=self._out)
        self._out = np.dot(self._out, self._x90, out=self._out)
        util.re_rot_z(v[2]-np.pi, self._rot_z)
        return np.dot(self._out, self._rot_z)

    def path(self, v):
        return ["QUBIT", list(v)]

    def assemble(self, v, i=0):
        # once you are done with the basics, expand this into its several steps
        return "Z({}) q{}\nX(pi/2) q{}\nZ({}) q{}\nX(pi/2) q{}\nZ({}) q{}\n".format(v[0], i, i, v[1] + np.pi, i, i, v[2]-np.pi, i)
    
    def __repr__(self):
        return "SingleQubitStep()"


class SingleQutritStep(QuantumStep):
    def __init__(self):
        self._num_inputs = 8
        self._dits = 1

    def matrix(self, v):
        return util.qt_arb_rot(*v)

    def path(self, v):
        return ["QUTRIT", list(v)]

    def assemble(self, v, i=0):
        return "U({}, {}, {}, {}, {}, {}, {}, {}) q{}".format(*v, i)
    
    def __repr__(self):
        return "SingleQutritStep()"

class UStep(QuantumStep):
    def __init__(self, U, name=None, dits=1):
        self.name = name
        self._num_inputs = 0
        self._U = U
        self._dits = dits

    def matrix(self, v):
        return self._U

    def path(self, v):
        if self.name is None:
            return ["CUSTOM", self._U]
        else:
            return [self.name]

    def assemble(self, v, i=0):
        if self.name is None:
            return "UNKNOWN q{}".format(i)
        elif self._dits == 1:
            return "{} q{}".format(self.name, i)
        else:
            return "{}".format(self.name)

    def __repr__(self):
        if self.name is None:
            return "UStep({})".format(repr(self._U))
        elif self._dits == 1:
            return "UStep({}, name={})".format(repr(self._U), repr(self.name))
        else:
            return "UStep({}, name={}, dits={})".format(repr(self._U), repr(self.name), repr(self._dits))

class CUStep(QuantumStep):
    def __init__(self, U, name=None, flipped=False):
        self.name = name
        self.flipped = flipped
        self._num_inputs = 0
        self._U = U
        n = np.shape(U)[0]
        I = np.matrix(np.eye(n))
        top = np.pad(self._U if flipped else I, [(0,n),(0,n)], 'constant')
        bot = np.pad(I if flipped else self._U, [(n,0),(n,0)], 'constant')
        self._CU = np.matrix(top + bot)
        self._dits = 2

    def matrix(self, v):
        return self._CU

    def path(self, v):
        if self.name is None:
            return [("FLIPPED " if self.flipped else "") + "C-CUSTOM", self._U]
        else:
            return [self.name]

    def assemble(self, v, i=0):
        first = i+1 if self.flipped else i
        second = i if self.flipped else i+1
        if self.name is None:
            return "CONTROLLED-UNKNOWN q{} q{}".format(first, second)
        else:
            return "C{} q{} q{}".format(self.name, first, second)

    def __repr__(self):
        return "CUStep(" + str(repr(self._U)) + ("" if self.name is None else ", name={}".format(repr(self.name))) + ("flipped=True" if self.flipped else "") + ")"

class InvertStep(QuantumStep):
    def __init__(self, step):
        self._step = step
        self._num_inputs = step._num_inputs
        self._dits = step._dits

    def matrix(self, v):
        return self._step.matrix(v).H

    def path(self, v):
        return ["INVERTED", self._step.path(v)]

    def assemble(self, v, i=0):
        return "REVERSE {\n" + self._step.assemble(v, i) + "\n}"

    def __repr__(self):
        return "InvertStep({})".format(repr(self._step))


class CSUMStep(QuantumStep):
    _csum =  np.matrix([[1,0,0, 0,0,0, 0,0,0],
                        [0,1,0, 0,0,0, 0,0,0],
                        [0,0,1, 0,0,0, 0,0,0],
                        [0,0,0, 0,0,1, 0,0,0],
                        [0,0,0, 1,0,0, 0,0,0],
                        [0,0,0, 0,1,0, 0,0,0],
                        [0,0,0, 0,0,0, 0,1,0],
                        [0,0,0, 0,0,0, 1,0,0],
                        [0,0,0, 0,0,0, 0,0,1]
                       ], dtype='complex128')
    
    def __init__(self):
        self._num_inputs = 0
        self._dits = 2

    def matrix(self, v):
        return CSUMStep._csum

    def path(self, v):
        return ["CSUM"]

    def assemble(self, v, i=0):
        return "CSUM q{} q{}".format(i, i+1)

    def __repr__(self):
        return "CSUMStep()"

class CPIStep(QuantumStep):
    _cpi = np.matrix([[1,0,0, 0,0,0, 0,0,0],
                      [0,1,0, 0,0,0, 0,0,0],
                      [0,0,1, 0,0,0, 0,0,0],
                      [0,0,0, 0,1,0,0,0,0],
                      [0,0,0, 1,0,0, 0,0,0],
                      [0,0,0, 0,0,1, 0,0,0],
                      [0,0,0, 0,0,0, 1,0,0],
                      [0,0,0, 0,0,0, 0,1,0],
                      [0,0,0, 0,0,0, 0,0,1]
                     ], dtype='complex128')
    
    def __init__(self):
        self._num_inputs = 0
        self._dits = 2

    def matrix(self, v):
        return CPIStep._cpi

    def path(self, v):
        return ["CPI"]

    def assemble(self, v, i=0):
        return "CPI q{} q{}".format(i, i+1)

    def __repr__(self):
        return "CPIStep()"

class CPIPhaseStep(QuantumStep):
    def __init__(self):
        self._num_inputs = 0
        self._cpi = np.matrix([[1,0,0, 0,0,0, 0,0,0],
                               [0,1,0, 0,0,0, 0,0,0],
                               [0,0,1, 0,0,0, 0,0,0],
                               [0,0,0, 0,-1,0,0,0,0],
                               [0,0,0, 1,0,0, 0,0,0],
                               [0,0,0, 0,0,1, 0,0,0],
                               [0,0,0, 0,0,0, 1,0,0],
                               [0,0,0, 0,0,0, 0,1,0],
                               [0,0,0, 0,0,0, 0,0,1]
                              ], dtype='complex128')
        diag_mod = np.matrix(np.diag([1]*4 + [np.exp(2j * np.random.random()*np.pi) for _ in range(0,5)]))
        self._cpi = np.matmul(self._cpi, diag_mod)
        self._dits = 2

    def matrix(self, v):
        return self._cpi

    def path(self, v):
        return ["CPI+"]

    def assemble(self, v, i=0):
        return "CPI- q{} q{}".format(i, i+1)

    def __repr__(self):
        return "CPIPhaseStep()"

class CNOTStep(QuantumStep):
    _cnot = np.matrix([[1,0,0,0],
                       [0,1,0,0],
                       [0,0,0,1],
                       [0,0,1,0]], dtype='complex128')
    def __init__(self):
        self._num_inputs = 0
        self._dits = 2

    def matrix(self, v):
        return CNOTStep._cnot

    def path(self, v):
        return ["CNOT"]

    def assemble(self, v, i=0):
        return "CNOT q{} q{}".format(i, i+1)

    def __repr__(self):
        return "CNOTStep()"

class CRZStep(QuantumStep):
    _cnr = np.matrix([[1,0,0,0],
                       [0,1,0,0],
                       [0,0,0.5+0.5j,0.5-0.5j],
                       [0,0,0.5-0.5j,0.5+0.5j]])
    _I = np.matrix(np.eye(2))
    def __init__(self):
        self._num_inputs = 1
        self._dits = 2

    def matrix(self, v):
        U = np.dot(CRZStep._cnr, np.kron(CRZStep._I, util.rot_z(v[0]))) # TODO fix this line
        return np.dot(U, CRZStep._cnr)

    def path(self, v):
        return ["CQ", v]

    def assemble(self, v, i=0):
        return "CNOTROOT q{} q{}\nZ({}) q{}\nCNOTROOT q{} q{}".format(i, i+1, v[0], i+1, i, i+1)

    def __repr__(self):
        return "CQubitStep()"

class RemapStep(QuantumStep):

    def __init__(self, step, dits, source, target, name=None, d=2):
        self._step = step
        self._source = source
        self._target = target
        self._dits = dits
        self._d = d
        self._name = name
        self._num_inputs = step._num_inputs
        def g(a,b):
            def f(i,j):
                i_v = []
                j_v = []
                for k in range(0, dits):
                    i_v.append(i%d)
                    j_v.append(j%d)
                    i = i // d
                    j = j // d
                j_v[b], j_v[a] = j_v[a], j_v[b]
                eq = np.equal(i_v, j_v)
                return np.all(eq, axis=0)
            return f
        targetswap = target if source == 1 else 1
        swap_source = np.matrix(np.fromfunction(g(0,source), (d**dits,d**dits)), dtype='complex128')
        swap_target = np.matrix(np.fromfunction(g(targetswap, target), (d**dits,d**dits)), dtype='complex128')
        self._prefix = np.dot(swap_source, swap_target)
        self._postfix = np.dot(swap_target, swap_source)


    def matrix(self, v):
       return util.matrix_product(self._prefix, np.kron(self._step.matrix(v), np.eye(self._d**(self._dits-2))), self._postfix)

    def assemble(self, v, i=0):
        if self._name == None:
            return "REMAP q{} q{} [{}]".format(self._source, self._target, self._step.assemble(v, i))
        else:
            return "{} q{} q{}".format(self._name, self._source, self._target)

    def __repr__(self):
        return "RemapStep({}, {}, {}, {}, name={}, d={})".format(self._step, self._dits, self._source, self._target, self._name, self._d)



class CNOTRootStep(QuantumStep):
    _cnr = np.matrix([[1,0,0,0],
                       [0,1,0,0],
                       [0,0,0.5+0.5j,0.5-0.5j],
                       [0,0,0.5-0.5j,0.5+0.5j]])
    def __init__(self):
        self._num_inputs = 0
        self._dits = 2

    def matrix(self, v):
        return CNOTRootStep._cnr

    def path(self, v):
        return ["CNOTROOT"]

    def assemble(self, v, i=0):
        return "CNOTROOT q{} q{}".format(i, i+1)

    def __repr__(self):
        return "CNOTRootStep()"

class KroneckerStep(QuantumStep):
    def __init__(self, *substeps):
        self._num_inputs = sum([step._num_inputs for step in substeps])
        self._substeps = substeps
        self._dits = sum([step._dits for step in substeps])

    def matrix(self, v):
        matrices = []
        index = 0
        for step in self._substeps:
            U = step.matrix(v[index:index+step._num_inputs])
            matrices.append(U)
            index += step._num_inputs
        U = matrices[0]
        for matrix in matrices[1:]:
            U = np.kron(U, matrix)
        return U

    def path(self, v):
        paths = ["KRON"]
        index = 0
        for step in self._substeps:
            p = step.path(v[index:index+step._num_inputs])
            paths.append(p)
            index += step._num_inputs
        return paths

    def assemble(self, v, i=0):
        outstr = ""
        index = 0
        for step in self._substeps:
            outstr += step.assemble(v[index:index+step._num_inputs], i) + "\n"
            index += step._num_inputs
            i += step._dits

        return outstr


    def appending(self, step):
        return KroneckerStep(*self._substeps, step)

    def __deepcopy__(self, memo):
        return KroneckerStep(self._substeps.__deepcopy__(memo))

    def __repr__(self):
        return "KroneckerStep({})".format(repr(self._substeps)[1:-1])

class ProductStep(QuantumStep):
    def __init__(self, *substeps):
        self._num_inputs = sum([step._num_inputs for step in substeps])
        self._substeps = substeps
        self._dits = 0 if len(substeps) == 0 else substeps[0]._dits

    def matrix(self, v):
        matrices = []
        index = 0
        for step in self._substeps:
            U = step.matrix(v[index:index+step._num_inputs])
            matrices.append(U)
            index += step._num_inputs
        U = matrices[0]
        for matrix in matrices[1:]:
            U = np.matmul(U, matrix)
        return U

    def path(self, v):
        paths = ["PRODUCT"]
        index = 0
        for step in self._substeps:
            p = step.path(v[index:index+step._num_inputs])
            paths.append(p)
            index += step._num_inputs
        return paths

    def assemble(self, v, i=0):
        outstr = ""
        index = 0
        for step in self._substeps:
            outstr += step.assemble(v[index:index+step._num_inputs], i) + "\n"
            index += step._num_inputs

        return outstr

    def appending(self, *steps):
        return ProductStep(*self._substeps, *steps)

    def __deepcopy__(self, memo):
        return ProductStep(self._substeps.__deepcopy__(memo))

    def __repr__(self):
        return "ProductStep({})".format(repr(self._substeps)[1:-1])

# WARNING: This is considered legacy code and may be deleted in the future, along with the path() function of the QuantumStep class.
def decode_path(path, d=2, args=None):
    if args is None:
        args = dict()
    if len(path) < 1:
        return (None,[])
    if path[0] == "KRON":
        k = []
        vf = []
        for item in path[1:]:
           (step, v) = decode_path(item, d, args)
           k.append(step)
           vf.extend(v)
        return (KroneckerStep(*k), vf)

    elif path[0] == "PRODUCT":
        p = []
        vf = []
        for item in path[1:]:
           (step, v) = decode_path(item, d, args)
           p.append(step)
           vf.extend(v)
        return (ProductStep(*p), vf)

    elif not path[0] in args:
        if path[0] == "IDENTITY":
            args[path[0]] = IdentityStep(d)
        elif path[0] == "QUBIT":
            args[path[0]] = SingleQubitStep()
        elif path[0] == "QUTRIT":
            args[path[0]] = SingleQutritStep()
        elif path[0] == "CNOT":
            args[path[0]] = CNOTStep()
        elif path[0] == "CQ":
            args[path[0]] = CQubitStep()
    return (args[path[0]], path[1] if len(path) > 1 else [])

