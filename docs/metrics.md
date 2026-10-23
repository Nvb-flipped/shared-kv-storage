# Placement, movement and request balance

<!-- navigation:start -->
[Project home](../README.md) / [Documentation map](README.md)
<!-- navigation:end -->

<!-- contents:start -->
On this page: [Integer placement](#integer-placement) · [Counts, shares and balance](#counts-shares-and-balance) · [Movement and transfer matrix](#movement-and-transfer-matrix) · [Expectations and fixed layouts](#expectations-and-fixed-layouts) · [Request balance and the hot key](#request-balance-and-the-hot-key) · [Membership cost](#membership-cost)
<!-- contents:end -->

Let the dataset be $\mathcal K$, with $K=|\mathcal K|>0$. There are $N$ active physical nodes before a join and $N+1$ afterward. $V$ is the number of tokens per node. These formulas concern the single-owner framework. A virtual token is a placement position, not another process.

## Integer placement

The router converts SHA-256's digest into an unsigned integer $H(k)$. Placement uses integers throughout; percentages are display data. For sorted member list $M$:

$$
o(k)=M[H(k)\bmod |M|].
$$

For sorted consistent-hash token positions $t_0,\ldots,t_{NV-1}$, the first token at or after a key owns it:

$$
j(k)=\min\{j:t_j\ge H(k)\},\qquad o(k)=\mathrm{host}(t_{j(k)}).
$$

If the set is empty, use $j(k)=0$ to wrap around. Tokens hash `node_id#i`, with zero-based index $i$. The CLI displays the router's returned owner and token index; it never repeats this calculation.

## Counts, shares and balance

If node $i$ owns $c_i$ keys, its share is:

$$
p_i=\frac{c_i}{K},\qquad \sum_i p_i=1.
$$

The specification's max/min ratio and the retained CV describe spread:

$$
R_{\mathrm{keys}}=\frac{\max_i c_i}{\min_i c_i}.
$$

$$
\bar c=\frac{K}{N},\qquad
\sigma=\sqrt{\frac{1}{N}\sum_{i=1}^{N}(c_i-\bar c)^2},\qquad
\mathrm{CV}=\frac{\sigma}{\bar c}.
$$

Use the active node count at each stage: N before joining and N+1 afterward (three and four in the historical reference). Standard deviation is in keys; CV measures spread relative to average load. Counts 90/110 and 900/1100 both give CV=0.10. CV is not a fraction of moved keys.

The ratio requires a positive minimum. If one node is empty and another is not, it is infinite; an all-empty ratio is undefined. JSON uses `null` for either case rather than a non-finite number. Empty shares and CV=0 are display conventions, not evidence of balanced placement. Reported experiments use nonempty datasets.

## Movement and transfer matrix

Let $o_0(k)$ and $o_1(k)$ be old and new physical owners returned by the router. The indicator $\mathbf 1[\cdot]$ is one when its condition holds.

$$
T_{ij}=\sum_{k\in\mathcal K}\mathbf 1[o_0(k)=i\ \land\ o_1(k)=j].
$$

Rows identify old owners and columns identify new owners. Diagonal cells stayed; off-diagonal cells moved. Row totals equal the old counts, column totals equal the new counts, and all entries sum to $K$.

$$
m=\sum_{i\ne j}T_{ij}=K-\sum_iT_{ii},\qquad
f_{\mathrm{move}}=\frac{m}{K},\qquad
f_{\mathrm{stay}}=1-f_{\mathrm{move}}.
$$

Every cell percentage uses all original keys: $100T_{ij}/K$. For joining node D:

$$
m_{\to D}=\sum_{i\ne D}T_{iD},\qquad
m_{\mathrm{old}}=\sum_{\substack{i\ne j\\i,j\ne D}}T_{ij},\qquad
m=m_{\to D}+m_{\mathrm{old}}.
$$

Modulo can shuffle keys among old nodes as well as send keys to D. Consistent hashing keeps old tokens fixed, so every changed primary becomes D. The experiment checks owner changes against acknowledged copies and verified destinations, then reads every original value and checks physical ownership. A movement calculation alone does not prove data transfer.

## Expectations and fixed layouts

For modulo, insert one new ID into the sorted membership. Under uniform residues modulo $N(N+1)$:

$$
\mathbb E[f_{\mathrm{move}}]=\frac{N}{N+1}.
$$

This predicts about 75% for three nodes growing to four. It is a uniform-hash model, not a finite-dataset guarantee. Inserting an ID at another sorted position changes transfer destinations, but not this expected total fraction.

Index the old nodes from zero. If an old node had index i and has new index j, a key stays there exactly when its remainders modulo N and modulo N+1 are i and j. Since the moduli are coprime, the Chinese remainder theorem gives one residue modulo their product for each old node's pair. There are N distinct staying residues among N(N+1), giving a staying fraction of 1/(N+1) and its complementary moved fraction. This applies at every insertion position. It uses a uniform-residue idealization; SHA-256 on a chosen finite dataset does not guarantee these frequencies.

With old tokens fixed, equal tokens per node and ideal exchangeable random token positions:

$$
m_{\mathrm{old}}=0,\qquad m=c_D^{\mathrm{after}},\qquad
\mathbb E[f_{\mathrm{move}}]=\frac{1}{N+1}.
$$

The 25% expectation averages over layouts. More virtual nodes can reduce coverage variation; they do not change that expectation to 12.5%. Improvement need not be monotonic for fixed node IDs.

Two arguments are separate here. Inserting only the new node's tokens leaves every old token fixed, so changed intervals can only acquire that new owner. Under the ideal exchangeable-position model with equal token counts, all N+1 physical labels have equal expected coverage. Their coverage sums to one, so each expected share is 1/(N+1). Repeating processes with the same IDs does not repeat that random-layout experiment.

For this particular ring, let $L=2^{256}$ and use distinct sorted token positions. Each token owns its clockwise predecessor interval. With at least two distinct positions, D's exact share of hash space is:

$$
q_D=\frac{1}{L}\sum_{j:\mathrm{host}(t_j)=D}
\left((t_j-t_{j-1})\bmod L\right).
$$

For uniformly distributed key hashes, $q_D$ is the expected captured fraction conditional on this ring. A token sequence uses one character per token, so columns show token rank rather than proportional hash-space distance. Coverage percentages use integer interval lengths separately.

## Request balance and the hot key

Router counters include forwarded client Put/Get attempts, including misses. Health, inventory, migration and `ring --check` probes are excluded. Inspection probes have a separate counter. Experiments reset counters after loading and verification.

For node $i$ serving $r_i$ of $Q>0$ reads:

$$
p_i^{\mathrm{read}}=\frac{r_i}{Q},\qquad
R_{\mathrm{requests}}=\frac{\max_i r_i}{\min_i r_i}.
$$

The ratio has the same zero-denominator qualifications as the key ratio. The original reference exercise sends $U=1000$ uniformly sampled reads, including the hot key, then adds $H=500$ reads to that key. It compares cumulative counts before and after those added reads. Thus $Q=U+H=1500$ and $\alpha=H/(U+H)=1/3$. Configurable runs use their recorded positive U and nonnegative H; the same formulas apply, including H=0.

$$
\mathbb E[p_h^{\mathrm{read}}]
=\alpha+(1-\alpha)\frac{c_h}{K}.
$$

Here $h$ is the hot key's owner. The background includes the hot key, so the fraction is $c_h/K$. The older $(c_h-1)/(K-1)$ expression applies only to a background excluding it, with $K>1$; that is not this experiment. Key counts stay unchanged while the configured extra requests reach $h$. Virtual nodes spread different keys, but one hot key still has one owner.

This follows by weighting counts: each background read reaches h with probability equal to its stored-key share, while every extra hot read reaches h. Divide the expected count by U+H. A finite seeded sequence can differ from that expectation. Custom runs replace the reference's 500 extra reads with their configured H and use their actual totals in tables and plots.

## Membership cost

Acknowledged copies, verified destinations and elapsed join seconds are measured. The calculated `estimated_item_bytes` serializes each acknowledged logical item as `{"key": key, "value": value}` with Python's default JSON separators and `ensure_ascii=False`, then counts its UTF-8 bytes.

$$
B_{\mathrm{estimate}}=\sum_{k\in\mathcal M_{\mathrm{ack}}}s(k).
$$

Here $s(k)$ is that byte length and $\mathcal M_{\mathrm{ack}}$ is the set of acknowledged copies. It is not measured HTTP or network traffic. Actual requests put keys in URLs and values in bodies; headers, responses, readback and deletion are outside this representation. The join timer includes preparation, copying, destination verification, publication and cleanup, and excludes the later independent exhaustive verification. Three fresh runs describe local timing variation; they do not sample independent token layouts or establish a universal optimum.

<!-- reading:start -->
[Documentation map](README.md) · Previous: [API reference](api.md) · Next: [Experiment design](experiment-design.md)
<!-- reading:end -->
