"""Auto Build: working a machine out from input/output examples."""


def ex_pair_check(inp, out):
    """The two Auto Build boxes, checked. Returns an error string, or None when they are usable.
    Both boxes are required: a Moore machine is defined by what it prints, so without an output
    there is nothing to aim at and every state could print the same symbol."""
    for label, text in (("Input String", inp), ("Expected Output", out)):
        gaps = [i for i, c in enumerate(text) if c.isspace()]
        if gaps:
            return (f"⚠️ {label} contains a space\n"
                    f"{label} has {len(gaps)} space(s); symbols go straight after each other with "
                    f"no gaps between them (the first is at position {gaps[0] + 1}).\n"
                    f"Fix: delete the spaces, so the box reads '{text.replace(' ', '')}'.")
    if not inp:
        return ("⚠️ Input String is empty\n"
                "There is nothing for the machine to read, so there is nothing to build.\n"
                "Fix: type the symbols to feed the machine, such as 10110.")
    if not out:
        return ("⚠️ Expected Output is empty\n"
                "A Moore machine is defined by what it prints, so an output is what makes the "
                "machine mean anything at all.\n"
                f"Fix: type what should come out for input '{inp}' - exactly {len(inp) + 1} "
                f"characters, such as {'0' * (len(inp) + 1)}.")
    if len(out) != len(inp) + 1:
        return (f"⚠️ Wrong output length\n"
                f"Input '{inp}' has {len(inp)} symbol(s), so its output must have {len(inp) + 1} - "
                f"you typed {len(out)}.\n"
                "Fix: the first output belongs to the start state and is printed before any input is read.")
    return None


def synthesize(examples):
    """Fit the fewest Moore states to (input, output) examples.
    Returns (states, initial, trans, defaulted): what to_dict() takes, plus how many transitions no
    example mentioned (each filled with a self-loop, so an input you never typed holds the state).
    Moore rule: the output is one symbol longer than the input - output[0] belongs to the start
    state and is printed before any input is read. Raises ValueError when nothing can fit."""
    seen = {}  # input prefix -> (the output printed there, an example it came from)
    for inp, out in examples:
        if len(out) != len(inp) + 1:
            raise ValueError(
                f"⚠️ Wrong output length\n"
                f"Input '{inp}' has {len(inp)} symbol(s), so its output must have {len(inp) + 1}.\n"
                "Fix: the first output belongs to the start state and is printed before any input is read.")
        for k in range(len(inp) + 1):
            p, want = inp[:k], out[k]
            if p in seen and seen[p][0] != want:
                raise ValueError(
                    f"⚠️ Conflicting examples\n"
                    f"After reading '{p}' one example needs output '{seen[p][0]}' but another needs '{want}'.\n"
                    f"(The examples '{seen[p][1]}' and '{inp}' disagree.)\n"
                    "Fix: no machine can satisfy both - correct or delete one of them.")
            seen[p] = (want, inp)
    if not seen:
        raise ValueError("⚠️ No examples yet\nThere is nothing to build a machine from.\n"
                         "Fix: type at least one line such as  10110 010110")

    alphabet = sorted({a for inp, _ in examples for a in inp})
    edges = {}  # only the transitions your examples actually justify
    for inp, _ in examples:
        for k, a in enumerate(inp):
            edges[(inp[:k], a)] = inp[:k + 1]

    def fit(order):
        """Fold states together in this order: two become one when they agree on every input they
        BOTH mention. An input neither one mentions is still free, so it never blocks a merge."""
        alive, tr, par = set(order), dict(edges), {s: s for s in order}
        while True:
            before = len(alive)
            for u in order:
                if u not in alive:
                    continue
                for v in order:
                    if v == u or v not in alive or seen[u][0] != seen[v][0]:
                        continue
                    if any((u, a) in tr and (v, a) in tr and tr[(u, a)] != tr[(v, a)] for a in alphabet):
                        continue
                    for a in alphabet:  # u keeps its own edges and borrows the ones only v had
                        if (u, a) not in tr and (v, a) in tr:
                            tr[(u, a)] = tr[(v, a)]
                        tr.pop((v, a), None)
                    for k in list(tr):  # everything that pointed at v now points at u
                        if tr[k] == v:
                            tr[k] = u
                    par[v] = u
                    alive.discard(v)
            if len(alive) == before:
                root = ""
                while par[root] != root:  # "" may have been folded away: follow it to what it became
                    root = par[root]
                return alive, tr, root

    # two scan orders: folding leaves first finds the small machine more often than roots first.
    # ponytail: greedy fold - near-minimal, not provably minimal (fewest states is NP-hard, and
    # scan order, refinement, and post-minimizing were all measured worse). Upgrade path: branch
    # and bound over output-homogeneous partitions when there are few prefixes, greedy above that.
    deep = sorted(seen, key=lambda s: (-len(s), s))
    shallow = sorted(seen, key=lambda s: (len(s), s))
    alive, tr, root = min((fit(deep), fit(shallow)), key=lambda r: len(r[0]))

    defaulted = 0
    for s in sorted(alive):  # an input your examples never mentioned holds the state
        for a in alphabet:
            if (s, a) not in tr:
                tr[(s, a)] = s
                defaulted += 1

    order, walked = [root], {root}
    i = 0
    while i < len(order):  # q0 is the start state; the rest are numbered in the shape of your examples
        s = order[i]
        i += 1
        for a in alphabet:
            t = tr[(s, a)]
            if t not in walked:
                walked.add(t)
                order.append(t)
    for s in sorted(alive):  # unreachable states cannot happen - but never silently drop one either
        if s not in walked:
            order.append(s)
    names = {s: f"q{i}" for i, s in enumerate(order)}
    states = {names[s]: seen[s][0] for s in order}
    trans = {(names[s], a): names[tr[(s, a)]] for s in order for a in alphabet}
    return states, names[root], trans, defaulted
