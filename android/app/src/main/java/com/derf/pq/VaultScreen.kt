package com.derf.pq

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chaquo.python.Python

@Composable
fun VaultUnlockScreen(
    profileName: String,
    onUnlocked: () -> Unit
) {
    var password by remember { mutableStateOf("") }
    var statusText by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ObsidianBackground)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "DERF POST-QUANTUM MESSENGER",
            color = ElectricCyan,
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(bottom = 8.dp)
        )

        Text(
            text = "Vault Profile: [${profileName.uppercase()}]",
            color = MutedText,
            fontSize = 14.sp,
            modifier = Modifier.padding(bottom = 32.dp)
        )

        Text(
            text = "Master Vault Password:",
            color = CrispWhite,
            fontSize = 14.sp,
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 8.dp)
        )

        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = InputSurface,
                unfocusedContainerColor = InputSurface,
                focusedBorderColor = ElectricCyan,
                unfocusedBorderColor = BorderColor,
                focusedTextColor = CrispWhite,
                unfocusedTextColor = CrispWhite
            ),
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .padding(bottom = 24.dp)
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Button(
                onClick = {
                    if (password.isBlank()) {
                        statusText = "Password required."
                        return@Button
                    }
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        derf.callAttr("set_profile", profileName)
                        val key = derf.callAttr("derive_vault", password)
                        derf.put("VAULT", key)
                        onUnlocked()
                    } catch (e: Exception) {
                        statusText = "Unlock Failed: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .weight(1f)
                    .height(52.dp)
            ) {
                Text("UNLOCK VAULT", fontWeight = FontWeight.Bold)
            }

            Button(
                onClick = {
                    if (password.isBlank()) {
                        statusText = "Password required."
                        return@Button
                    }
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        derf.callAttr("set_profile", profileName)
                        val key = derf.callAttr("derive_vault", password)
                        derf.put("VAULT", key)
                        onUnlocked()
                    } catch (e: Exception) {
                        statusText = "Creation Failed: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = CardSurface, contentColor = CrispWhite),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .weight(1f)
                    .height(52.dp)
            ) {
                Text("CREATE VAULT", fontWeight = FontWeight.Bold)
            }
        }

        if (statusText.isNotBlank()) {
            Text(
                text = statusText,
                color = ErrorRed,
                fontSize = 13.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 16.dp)
            )
        }
    }
}
