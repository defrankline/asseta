package com.asseta.core.ui.session

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.asseta.core.ui.AppRole
import com.asseta.core.ui.R
import com.asseta.core.ui.theme.AssetaColors

@Composable
fun LoginScreen(role: AppRole, state: SessionState.SignedOut, onSignIn: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().background(AssetaColors.Slate).padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Image(
            painter = painterResource(R.drawable.asseta_mark),
            contentDescription = stringResource(R.string.logo_description),
            modifier = Modifier.size(112.dp),
        )
        Spacer(Modifier.height(24.dp))
        Text(stringResource(R.string.asseta_brand), style = MaterialTheme.typography.headlineLarge, color = Color.White)
        Text(stringResource(role.label), style = MaterialTheme.typography.titleMedium, color = AssetaColors.Amber)
        Spacer(Modifier.height(8.dp))
        Text(stringResource(role.tagline), style = MaterialTheme.typography.bodyMedium, color = Color.White.copy(alpha = 0.8f))
        Spacer(Modifier.height(48.dp))
        if (state.busy) {
            CircularProgressIndicator(color = AssetaColors.Amber)
            Spacer(Modifier.height(12.dp))
            Text(stringResource(R.string.signing_in), color = Color.White)
        } else {
            Button(
                onClick = onSignIn,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = AssetaColors.Amber, contentColor = AssetaColors.OnAmber),
            ) { Text(stringResource(R.string.sign_in)) }
        }
        state.error?.let { ErrorText(it, Color(0xFFFFB4AB)) }
    }
}

@Composable
internal fun ErrorText(error: UiError, color: Color = MaterialTheme.colorScheme.error) {
    Spacer(Modifier.height(16.dp))
    Text(error.message, color = color, textAlign = TextAlign.Center)
    error.reference?.let {
        Text(stringResource(R.string.error_reference, it), color = color, style = MaterialTheme.typography.bodySmall)
    }
}
