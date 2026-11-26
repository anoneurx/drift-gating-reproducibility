#!/usr/bin/env python3
"""
tests/external_validation/ref_policies.py
Independent textbook/paper reference implementations of:
  - LRU
  - FIFO
  - ARC (Megiddo & Modha, FAST 2003)
  - S3-FIFO (Yang et al., SOSP 2023, strict S+M <= C invariant)
  - SIEVE (Zhang et al., NSDI 2024, Algorithm 1)
"""
from collections import OrderedDict, deque


class RefLRU:
    def __init__(self, C: int):
        self.C = C
        self.od = OrderedDict()

    def access(self, x: int) -> bool:
        if x in self.od:
            self.od.move_to_end(x, last=False)  # front = MRU
            return True
        if len(self.od) >= self.C:
            self.od.popitem(last=True)  # back = LRU
        self.od[x] = None
        self.od.move_to_end(x, last=False)
        return False


class RefFIFO:
    def __init__(self, C: int):
        self.C = C
        self.q = deque()
        self.s = set()

    def access(self, x: int) -> bool:
        if x in self.s:
            return True
        if len(self.q) >= self.C:
            v = self.q.pop()
            self.s.remove(v)
        self.q.appendleft(x)
        self.s.add(x)
        return False


class RefARC:
    """Megiddo & Modha (FAST 2003) ARC."""
    def __init__(self, C: int):
        self.C = C
        self.p = 0.0
        self.t1 = OrderedDict()
        self.t2 = OrderedDict()
        self.b1 = OrderedDict()
        self.b2 = OrderedDict()

    def _replace(self, x: int):
        in_b2 = x in self.b2
        if len(self.t1) > 0 and (len(self.t1) > self.p or (in_b2 and len(self.t1) == self.p)):
            v, _ = self.t1.popitem(last=True)
            self.b1[v] = None
            self.b1.move_to_end(v, last=False)
        elif len(self.t2) > 0:
            v, _ = self.t2.popitem(last=True)
            self.b2[v] = None
            self.b2.move_to_end(v, last=False)

    def access(self, x: int) -> bool:
        if x in self.t1:
            del self.t1[x]
            self.t2[x] = None
            self.t2.move_to_end(x, last=False)
            return True
        if x in self.t2:
            self.t2.move_to_end(x, last=False)
            return True
        if x in self.b1:
            d = max(1.0, len(self.b2) / max(1, len(self.b1)))
            self.p = min(float(self.C), self.p + d)
            self._replace(x)
            del self.b1[x]
            self.t2[x] = None
            self.t2.move_to_end(x, last=False)
            return False
        if x in self.b2:
            d = max(1.0, len(self.b1) / max(1, len(self.b2)))
            self.p = max(0.0, self.p - d)
            self._replace(x)
            del self.b2[x]
            self.t2[x] = None
            self.t2.move_to_end(x, last=False)
            return False

        L1 = len(self.t1) + len(self.b1)
        if L1 >= self.C:
            if len(self.t1) < self.C:
                self.b1.popitem(last=True)
                self._replace(x)
            else:
                self.t1.popitem(last=True)
        else:
            tot = L1 + len(self.t2) + len(self.b2)
            if tot >= self.C:
                if tot >= 2 * self.C and len(self.b2) > 0:
                    self.b2.popitem(last=True)
                self._replace(x)
        self.t1[x] = None
        self.t1.move_to_end(x, last=False)
        return False


class RefS3FIFO:
    """Yang et al. (SOSP 2023) S3-FIFO with strict S + M <= C invariant."""
    def __init__(self, C: int):
        self.C = C
        self.S_cap = max(1, round(0.10 * C))
        self.M_cap = C - self.S_cap
        if self.M_cap < 1:
            self.M_cap = max(1, C - 1)
            self.S_cap = C - self.M_cap
        self.S = deque()
        self.M = deque()
        self.G = OrderedDict()
        self.in_S = set()
        self.in_M = set()
        self.freq = {}

    def _evict_M(self):
        while self.M:
            t = self.M.pop()
            if self.freq[t] > 0:
                self.freq[t] -= 1
                self.M.appendleft(t)
            else:
                self.in_M.remove(t)
                del self.freq[t]
                return

    def _evict_S(self) -> bool:
        """Pop from S; return True if an item was actually evicted to G."""
        t = self.S.pop()
        self.in_S.remove(t)
        if self.freq[t] > 0 and self.M_cap > 0:
            self.freq[t] = 0
            if len(self.M) >= self.M_cap:
                self._evict_M()
            self.M.appendleft(t)
            self.in_M.add(t)
            return False
        else:
            del self.freq[t]
            self.G[t] = None
            self.G.move_to_end(t, last=False)
            if len(self.G) > max(1, self.M_cap):
                self.G.popitem(last=True)
            return True

    def _evict(self):
        while len(self.S) + len(self.M) >= self.C:
            if len(self.S) >= self.S_cap or len(self.M) == 0:
                if len(self.S) == 0:
                    self._evict_M()
                    return
                evicted = self._evict_S()
                if evicted:
                    return
            else:
                self._evict_M()
                return

    def access(self, x: int) -> bool:
        if x in self.in_S or x in self.in_M:
            self.freq[x] = min(3, self.freq[x] + 1)
            return True
        in_g = x in self.G
        if in_g:
            del self.G[x]
        self._evict()
        self.freq[x] = 0
        if in_g:
            self.M.appendleft(x)
            self.in_M.add(x)
        else:
            self.S.appendleft(x)
            self.in_S.add(x)
        return False


class RefSIEVE:
    """Zhang et al. (NSDI 2024) SIEVE Algorithm 1."""
    def __init__(self, C: int):
        self.C = C
        self.q = []  # index 0 = head (newest), -1 = tail (oldest)
        self.in_set = set()
        self.visited = {}
        self.hand = None  # index into self.q

    def access(self, x: int) -> bool:
        if x in self.in_set:
            self.visited[x] = True
            return True
        if len(self.q) >= self.C:
            idx = (len(self.q) - 1) if self.hand is None else self.hand
            while self.visited[self.q[idx]]:
                self.visited[self.q[idx]] = False
                idx = (len(self.q) - 1) if idx == 0 else (idx - 1)
            v = self.q[idx]
            self.q.pop(idx)
            self.in_set.remove(v)
            del self.visited[v]
            if not self.q:
                self.hand = None
            else:
                self.hand = (len(self.q) - 1) if idx == 0 else (idx - 1)
        self.q.insert(0, x)
        if self.hand is not None:
            self.hand += 1  # shifted right by insert(0, x)
        self.in_set.add(x)
        self.visited[x] = False
        return False
