package com.asseta.core.sync

import android.os.SystemClock

/** Wall clock (device time, recorded as-is) and the monotonic clock used for tamper detection. Fakeable in tests. */
interface SyncClock {
    fun nowMs(): Long
    fun elapsedRealtimeMs(): Long
}

object SystemSyncClock : SyncClock {
    override fun nowMs(): Long = System.currentTimeMillis()
    override fun elapsedRealtimeMs(): Long = SystemClock.elapsedRealtime()
}
