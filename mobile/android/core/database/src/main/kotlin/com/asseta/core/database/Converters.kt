package com.asseta.core.database

import androidx.room.TypeConverter
import com.asseta.core.model.ClientOperationStatus

/** Enums are stored by name (stable, readable); never by ordinal. */
class Converters {
    @TypeConverter
    fun statusToString(status: ClientOperationStatus): String = status.name

    @TypeConverter
    fun stringToStatus(raw: String): ClientOperationStatus = ClientOperationStatus.valueOf(raw)
}
