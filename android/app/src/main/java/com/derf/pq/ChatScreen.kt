package com.derf.pq

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chaquo.python.Python

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatComposeScreen() {
    val clipboardManager = androidx.compose.ui.platform.LocalClipboardManager.current
    var activePeer by remember { mutableStateOf<String?>(null) }
    var contactsList by remember { mutableStateOf<List<String>>(emptyList()) }
    var chatTranscript by remember { mutableStateOf("Welcome to Derf PQ Messenger.\n[Select a recipient above to begin confidential communication]\n") }
    var messageText by remember { mutableStateOf("") }
    var packetText by remember { mutableStateOf("") }
    var bannerStatus by remember { mutableStateOf("") }

    // Load active contacts on entry
    LaunchedEffect(Unit) {
        try {
            val py = Python.getInstance()
            val derf = py.getModule("Derf")
            val keys = derf.callAttr("contacts_list").asList()
            contactsList = keys.map { it.toString() }
            if (contactsList.isNotEmpty() && activePeer == null) {
                activePeer = contactsList[0]
            }
        } catch (e: Exception) {
            bannerStatus = "Error loading contacts: ${e.message}"
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ObsidianBackground)
            .padding(16.dp)
    ) {
        // Apple HIG Recipient Header Row
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "ACTIVE RECIPIENT",
                color = MutedText,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            if (activePeer != null) {
                Surface(
                    color = ActiveGreen.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = "SECURE RATCHET READY",
                        color = ActiveGreen,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                    )
                }
            }
        }

        if (contactsList.isEmpty()) {
            Surface(
                color = CardSurface,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, BorderColor, RoundedCornerShape(12.dp))
                    .padding(bottom = 12.dp)
            ) {
                Text(
                    text = "No saved contacts. Add contacts in Contacts tab to start messaging.",
                    color = MutedText,
                    fontSize = 13.sp,
                    modifier = Modifier.padding(14.dp)
                )
            }
        } else {
            // Apple HIG Segmented Contact Cards Horizontal Row
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 12.dp)
            ) {
                items(contactsList) { peer ->
                    val isSelected = peer == activePeer
                    Surface(
                        onClick = {
                            activePeer = peer
                            bannerStatus = "Switched active recipient to '$peer'"
                        },
                        shape = RoundedCornerShape(16.dp),
                        color = if (isSelected) CardSurface else ObsidianBackground,
                        modifier = Modifier.border(
                            width = if (isSelected) 1.5.dp else 1.dp,
                            color = if (isSelected) ElectricCyan else BorderColor,
                            shape = RoundedCornerShape(16.dp)
                        )
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
                        ) {
                            // Avatar Circle with Contact Initial
                            Box(
                                contentAlignment = Alignment.Center,
                                modifier = Modifier
                                    .size(28.dp)
                                    .background(
                                        color = if (isSelected) ElectricCyan else InputSurface,
                                        shape = CircleShape
                                    )
                            ) {
                                Text(
                                    text = peer.take(1).uppercase(),
                                    color = if (isSelected) ObsidianBackground else CrispWhite,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            Spacer(modifier = Modifier.width(10.dp))
                            Text(
                                text = peer,
                                fontSize = 13.sp,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                color = if (isSelected) CrispWhite else MutedText
                            )
                        }
                    }
                }
            }
        }

        // Chat Transcript Container (Apple Glass Card)
        Surface(
            color = CardSurface,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .border(1.dp, BorderColor, RoundedCornerShape(16.dp))
                .padding(bottom = 12.dp)
        ) {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(14.dp)
            ) {
                item {
                    Text(
                        text = chatTranscript,
                        color = CrispWhite,
                        fontSize = 14.sp,
                        lineHeight = 20.sp
                    )
                }
            }
        }

        if (bannerStatus.isNotBlank()) {
            Text(
                text = bannerStatus,
                color = ElectricCyan,
                fontSize = 12.sp,
                modifier = Modifier.padding(bottom = 8.dp)
            )
        }

        // Decryption Section
        Text(
            text = "DECRYPT INCOMING PACKET",
            color = MutedText,
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp,
            modifier = Modifier.padding(bottom = 4.dp)
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = packetText,
                onValueChange = { packetText = it },
                placeholder = { Text("Paste DERF:V1: packet...", color = MutedText, fontSize = 13.sp) },
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
                    .weight(1f)
                    .height(52.dp)
            )

            Button(
                onClick = {
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val input = packetText.ifBlank { derf.callAttr("safe_paste").toString() }
                        if (input.contains("DERF:V1:")) {
                            val decrypted = derf.callAttr("decrypt_alien_stack", input, derf.callAttr("ensure_identity")).toString()
                            if (decrypted.isNotBlank() && decrypted != "None") {
                                chatTranscript += "\n[Peer]: $decrypted\n"
                                packetText = ""
                                bannerStatus = "Decrypted Message: $decrypted"
                            } else {
                                bannerStatus = "Decryption Failed: Stale packet or session key error."
                            }
                        } else {
                            bannerStatus = "Provide a valid DERF:V1: packet."
                        }
                    } catch (e: Exception) {
                        bannerStatus = "Decryption Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.height(52.dp)
            ) {
                Text("DECRYPT", fontWeight = FontWeight.Bold)
            }
        }

        // Composer Section
        Text(
            text = "COMPOSE MESSAGE",
            color = MutedText,
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp,
            modifier = Modifier.padding(bottom = 4.dp)
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = messageText,
                onValueChange = { messageText = it },
                placeholder = { Text("Type confidential message...", color = MutedText, fontSize = 13.sp) },
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
                    .weight(1f)
                    .height(52.dp)
            )

            Button(
                onClick = {
                    if (messageText.isBlank()) return@Button
                    if (activePeer == null) {
                        bannerStatus = "Error: Select or add a contact first."
                        return@Button
                    }
                    try {
                        val py = Python.getInstance()
                        val derf = py.getModule("Derf")
                        val cipherText = derf.callAttr("encrypt_alien_stack", messageText, activePeer, derf.callAttr("ensure_identity")).toString()
                        if (cipherText.isNotBlank() && cipherText != "None") {
                            clipboardManager.setText(androidx.compose.ui.text.AnnotatedString(cipherText))
                            derf.callAttr("safe_copy", cipherText)
                            chatTranscript += "\n[Me -> $activePeer]: $messageText\n[Ciphertext copied to clipboard]\n"
                            messageText = ""
                            bannerStatus = "DERF Ciphertext copied to clipboard!"
                        } else {
                            bannerStatus = "Encryption Failed: Perform handshake pairing first."
                        }
                    } catch (e: Exception) {
                        bannerStatus = "Encryption Error: ${e.message}"
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.height(52.dp)
            ) {
                Text("ENCRYPT", fontWeight = FontWeight.Bold)
            }
        }
    }
}
