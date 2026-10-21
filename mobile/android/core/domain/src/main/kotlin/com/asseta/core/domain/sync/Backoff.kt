package com.asseta.core.domain.sync

/**
 * Exponential backoff with "equal jitter": the cap doubles per consecutive failure (bounded by [maxMs]) and the
 * delay is uniformly drawn from [cap/2, cap], so many devices reconnecting together do not retry in lockstep.
 */
class Backoff(private val baseMs: Long = 15_000, private val maxMs: Long = 30 * 60_000) {
    init {
        require(baseMs > 0 && maxMs >= baseMs)
    }

    fun capFor(failures: Int): Long {
        if (failures <= 0) return 0
        val shift = (failures - 1).coerceAtMost(30)
        val exp = baseMs.toDouble() * (1L shl shift)
        return minOf(maxMs.toDouble(), exp).toLong()
    }

    /** [random] in [0, 1). Zero failures => no delay. */
    fun delayFor(failures: Int, random: Double): Long {
        require(random in 0.0..1.0)
        val cap = capFor(failures)
        return cap / 2 + (random * (cap - cap / 2)).toLong()
    }
}
