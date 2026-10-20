//! E7: per-decision cost of AgentSeg's group table against IMS-style per-pair rules.
//!
//! Inputs (little-endian u32 arrays from e7/prep_e7.py): member, rules, queries, random,
//! subset_rules, subset_queries, pairwise. Structures:
//!   group-hash   member[pod] -> group; HashSet of packed (src group, rel, dst group)
//!   group-sorted member[pod] -> group; per (src group, rel) a sorted Vec of dst groups, binary search
//!   pair-hash    HashSet of packed (src pod, dst pod, rel): IMS's compiled flow rules (subset only)
//! Each structure answers every query; time per decision is the best of 5 passes. Multi-thread
//! scaling splits the query array across std::thread::scope workers.
//! Usage: agentseg_bench <dir with the .u32 files>   (prints one JSON object)

use std::collections::{HashMap, HashSet};
use std::hash::{BuildHasherDefault, Hasher};
use std::time::Instant;

/// Integer hasher with full avalanche (MurmurHash3's 64-bit finalizer). A multiply-only hash
/// (FxHash) leaves the low bits of the hash depending only on the low bits of the key, which
/// clusters keys whose low bits vary little (the per-pair key ends in the relation), so every
/// structure uses this mixer.
#[derive(Default)]
struct Fx(u64);
impl Hasher for Fx {
    fn finish(&self) -> u64 {
        let mut x = self.0;
        x ^= x >> 33;
        x = x.wrapping_mul(0xff51afd7ed558ccd);
        x ^= x >> 33;
        x = x.wrapping_mul(0xc4ceb9fe1a85ec53);
        x ^ (x >> 33)
    }
    fn write(&mut self, bytes: &[u8]) {
        for &b in bytes {
            self.0 = (self.0 << 8) ^ b as u64;
        }
    }
    fn write_u64(&mut self, x: u64) {
        self.0 ^= x;
    }
}
type FxSet = HashSet<u64, BuildHasherDefault<Fx>>;
type FxMap<V> = HashMap<u64, V, BuildHasherDefault<Fx>>;

fn read_u32(path: &str) -> Vec<u32> {
    let b = std::fs::read(path).unwrap_or_else(|e| panic!("{path}: {e}"));
    b.chunks_exact(4).map(|c| u32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect()
}

fn triples(v: &[u32]) -> Vec<(u32, u32, u32)> {
    v.chunks_exact(3).map(|c| (c[0], c[1], c[2])).collect()
}

#[inline]
fn gkey(s: u32, r: u32, d: u32) -> u64 {
    ((s as u64) << 32) | ((r as u64) << 24) | d as u64
}
#[inline]
fn pkey(s: u32, r: u32, d: u32) -> u64 {
    ((s as u64) << 36) | ((d as u64) << 12) | r as u64
}

struct GroupHash {
    member: Vec<u32>,
    rules: FxSet,
}
impl GroupHash {
    #[inline]
    fn allow(&self, s: u32, d: u32, r: u32) -> bool {
        self.rules.contains(&gkey(self.member[s as usize], r, self.member[d as usize]))
    }
}

struct GroupSorted {
    member: Vec<u32>,
    rows: FxMap<Vec<u32>>,
}
impl GroupSorted {
    #[inline]
    fn allow(&self, s: u32, d: u32, r: u32) -> bool {
        let gs = self.member[s as usize];
        match self.rows.get(&(((gs as u64) << 8) | r as u64)) {
            Some(v) => v.binary_search(&self.member[d as usize]).is_ok(),
            None => false,
        }
    }
}

struct PairHash {
    rules: FxSet,
}
impl PairHash {
    #[inline]
    fn allow(&self, s: u32, d: u32, r: u32) -> bool {
        self.rules.contains(&pkey(s, r, d))
    }
}

/// Best-of-5 nanoseconds per decision and the number of allowed queries.
fn bench<F: Fn(u32, u32, u32) -> bool + Sync>(q: &[(u32, u32, u32)], f: &F) -> (f64, usize) {
    let mut best = f64::MAX;
    let mut allowed = 0;
    for _ in 0..5 {
        let t = Instant::now();
        let mut n = 0usize;
        for &(s, d, r) in q {
            n += f(s, d, r) as usize;
        }
        let dt = t.elapsed().as_secs_f64();
        allowed = std::hint::black_box(n);
        best = best.min(dt);
    }
    (1e9 * best / q.len() as f64, allowed)
}

/// Decisions per second with `threads` workers over the whole query array (best of 3).
fn throughput<F: Fn(u32, u32, u32) -> bool + Sync>(q: &[(u32, u32, u32)], f: &F, threads: usize) -> f64 {
    let mut best = 0f64;
    for _ in 0..3 {
        let chunk = (q.len() + threads - 1) / threads;
        let t = Instant::now();
        let total: usize = std::thread::scope(|sc| {
            let hs: Vec<_> = q
                .chunks(chunk)
                .map(|part| sc.spawn(move || part.iter().filter(|&&(s, d, r)| f(s, d, r)).count()))
                .collect();
            hs.into_iter().map(|h| h.join().unwrap()).sum()
        });
        std::hint::black_box(total);
        best = best.max(q.len() as f64 / t.elapsed().as_secs_f64());
    }
    best
}

fn hash_bytes(n: usize, cap: usize) -> usize {
    // hashbrown: one 8-byte slot plus one control byte per bucket
    let _ = n;
    cap * 9
}

fn main() {
    let dir = std::env::args().nth(1).expect("data dir");
    let p = |n: &str| format!("{dir}/{n}");
    let member = read_u32(&p("member.u32"));
    let rules = triples(&read_u32(&p("rules.u32")));
    let queries = triples(&read_u32(&p("queries.u32")));
    let random = triples(&read_u32(&p("random.u32")));
    let srules = triples(&read_u32(&p("subset_rules.u32")));
    let squeries = triples(&read_u32(&p("subset_queries.u32")));
    let pairwise = triples(&read_u32(&p("pairwise.u32")));

    let t = Instant::now();
    let gh = GroupHash { member: member.clone(), rules: rules.iter().map(|&(s, r, d)| gkey(s, r, d)).collect() };
    let build_gh = t.elapsed().as_secs_f64();
    let t = Instant::now();
    let mut rows: FxMap<Vec<u32>> = FxMap::default();
    for &(s, r, d) in &rules {
        rows.entry(((s as u64) << 8) | r as u64).or_default().push(d);
    }
    for v in rows.values_mut() {
        v.sort_unstable();
        v.dedup();
    }
    let gs = GroupSorted { member: member.clone(), rows };
    let build_gs = t.elapsed().as_secs_f64();
    let sub_gh = GroupHash { member: member.clone(), rules: srules.iter().map(|&(s, r, d)| gkey(s, r, d)).collect() };
    let t = Instant::now();
    let ph = PairHash { rules: pairwise.iter().map(|&(s, d, r)| pkey(s, r, d)).collect() };
    let build_ph = t.elapsed().as_secs_f64();

    // the two group structures and, on the subset, group vs per-pair must agree on every query
    for &(s, d, r) in queries.iter().take(2_000_000).chain(random.iter().take(2_000_000)) {
        assert_eq!(gh.allow(s, d, r), gs.allow(s, d, r));
    }
    for &(s, d, r) in &squeries {
        assert_eq!(sub_gh.allow(s, d, r), ph.allow(s, d, r), "subset mismatch");
    }

    let f_gh = |s, d, r| gh.allow(s, d, r);
    let f_gs = |s, d, r| gs.allow(s, d, r);
    let f_sub = |s, d, r| sub_gh.allow(s, d, r);
    let f_ph = |s, d, r| ph.allow(s, d, r);
    let (gh_obs, gh_obs_allow) = bench(&queries, &f_gh);
    let (gh_rnd, gh_rnd_allow) = bench(&random, &f_gh);
    let (gs_obs, _) = bench(&queries, &f_gs);
    let (gs_rnd, _) = bench(&random, &f_gs);
    let (sub_obs, _) = bench(&squeries, &f_sub);
    let (ph_obs, _) = bench(&squeries, &f_ph);

    // membership update (relabel): one store per event
    let mut m2 = member.clone();
    let t = Instant::now();
    let n_upd = 10_000_000usize;
    for i in 0..n_upd {
        let k = (i.wrapping_mul(2654435761)) % m2.len();
        m2[k] = (i % 16291) as u32;
    }
    std::hint::black_box(&m2);
    let upd_ns = 1e9 * t.elapsed().as_secs_f64() / n_upd as f64;

    let cores = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1);
    let mut scale = Vec::new();
    for th in [1usize, 2, 4, 6, 8, 12] {
        if th <= cores {
            scale.push(format!("{{\"threads\":{th},\"decisions_per_s\":{:.0}}}", throughput(&queries, &f_gh, th)));
        }
    }
    println!(
        "{{\"pods\":{},\"groups_rules\":{},\"queries\":{},\"observed_allowed\":{},\"random_allowed\":{},\
         \"group_hash_ns_observed\":{:.2},\"group_hash_ns_random\":{:.2},\"group_sorted_ns_observed\":{:.2},\
         \"group_sorted_ns_random\":{:.2},\"subset_queries\":{},\"subset_group_hash_ns\":{:.2},\"subset_pair_hash_ns\":{:.2},\
         \"pairwise_rules\":{},\"build_group_hash_s\":{:.4},\"build_group_sorted_s\":{:.4},\"build_pair_hash_s\":{:.4},\
         \"group_hash_bytes\":{},\"member_bytes\":{},\"pair_hash_bytes\":{},\"relabel_ns\":{:.2},\"cores\":{},\"scaling\":[{}]}}",
        member.len(), rules.len(), queries.len(), gh_obs_allow, gh_rnd_allow, gh_obs, gh_rnd, gs_obs, gs_rnd,
        squeries.len(), sub_obs, ph_obs, pairwise.len(), build_gh, build_gs, build_ph,
        hash_bytes(gh.rules.len(), gh.rules.capacity()), 4 * member.len(),
        hash_bytes(ph.rules.len(), ph.rules.capacity()), upd_ns, cores, scale.join(",")
    );
}
