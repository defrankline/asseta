package com.asseta.core.database

import androidx.room.migration.Migration

/**
 * Every schema change bumps [AssetaDatabase.VERSION], commits the exported schema JSON under
 * `schemas/`, and adds an explicit [Migration] (or a Room AutoMigration) here with a migration test.
 * Destructive fallback is never enabled: the outbox may hold unsynced field evidence.
 */
object AssetaMigrations {
    val ALL: Array<Migration> = emptyArray()
}
