package com.asseta.core.sync

import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.engine.LocalDataWiper
import com.asseta.core.sync.engine.SyncEngine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.net.ServerSocket
import java.util.concurrent.TimeUnit

/**
 * The background worker stops a run when its constraints go (the network dropped): the run must stop promptly, never
 * block the caller's thread, and leave no failure behind.
 */
@RunWith(RobolectricTestRunner::class)
class SyncCancellationTest : SyncTestBase() {

    @Test
    fun aStoppedRunCancelsTheHangingCallPromptlyAndRecordsNoFailure() = runBlocking {
        // Accepts connections (OS backlog) but never answers: the call would wait for the 30 s read timeout.
        ServerSocket(0).use { silent ->
            val client = NetworkFactory.okHttpClient({ "token" }, { null }, device = { DEVICE })
            val engine = SyncEngine(
                api = NetworkFactory.syncApi("http://127.0.0.1:${silent.localPort}/", client, allowCleartext = true),
                db = { db }, files = files, deviceId = { DEVICE }, appVersion = "0.1.0-test",
                wiper = LocalDataWiper { wipes += it }, clock = clock, json = json, account = { account }, random = { 0.5 },
            )
            val run = launch(Dispatchers.Default) { engine.sync(tenant) }
            delay(500)
            val started = System.nanoTime()
            run.cancelAndJoin()
            val tookMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started)
            assertTrue("cancel took $tookMs ms", tookMs < 3_000)
            assertTrue(run.isCancelled)
            assertEquals(0, db.syncStateDao().get(tenant)?.failureStreak ?: 0)
        }
    }

    @Test
    fun aRunStartedOnTheCallersThreadWorksElsewhere() = runBlocking {
        val caller = Thread.currentThread()
        var syncThread: Thread? = null
        val engine = SyncEngine(
            api = NetworkFactory.syncApi(server.url("/").toString(), NetworkFactory.okHttpClient({ "token" }, { null }, device = { DEVICE }), allowCleartext = true),
            db = { db }, files = files, deviceId = { DEVICE }, appVersion = "0.1.0-test",
            wiper = LocalDataWiper { wipes += it }, clock = clock, json = json,
            account = { syncThread = Thread.currentThread(); account }, random = { 0.5 },
        )
        // The UI's "Sync now" calls from the main thread: the run's database and file work happens elsewhere.
        val report = async { engine.sync(tenant) }.await()
        assertTrue("$report", report is com.asseta.core.sync.engine.SyncReport.Success)
        assertNotEquals(caller, syncThread)
    }
}
