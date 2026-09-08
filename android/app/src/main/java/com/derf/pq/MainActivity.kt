package com.derf.pq

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.Group
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Initialize Chaquopy In-Process Python Engine
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        setContent {
            DerfStitchTheme {
                MainAppScreen()
            }
        }
    }
}

sealed class Screen(val route: String, val title: String, val icon: ImageVector) {
    object Chat : Screen("chat", "Chat", Icons.Default.Chat)
    object Contacts : Screen("contacts", "Contacts", Icons.Default.Group)
    object Pairing : Screen("pairing", "Pairing", Icons.Default.Sync)
    object Identity : Screen("identity", "Identity", Icons.Default.Fingerprint)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainAppScreen() {
    var isUnlocked by remember { mutableStateOf(false) }
    var activeScreen by remember { mutableStateOf<Screen>(Screen.Chat) }
    var profileName by remember { mutableStateOf("default") }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        if (!isUnlocked) {
            VaultUnlockScreen(
                profileName = profileName,
                onUnlocked = { isUnlocked = true }
            )
        } else {
            Scaffold(
                topBar = {
                    TopAppBar(
                        title = {
                            Text(
                                text = "DERF PQ MESSENGER",
                                color = MaterialTheme.colorScheme.primary,
                                style = MaterialTheme.typography.titleMedium
                            )
                        },
                        actions = {
                            IconButton(onClick = { isUnlocked = false }) {
                                Icon(
                                    imageVector = Icons.Default.Lock,
                                    contentDescription = "Lock Vault",
                                    tint = MaterialTheme.colorScheme.primary
                                )
                            }
                        },
                        colors = TopAppBarDefaults.topAppBarColors(
                            containerColor = MaterialTheme.colorScheme.background
                        )
                    )
                },
                bottomBar = {
                    NavigationBar(
                        containerColor = CardSurface,
                        tonalElevation = 8.dp
                    ) {
                        val screens = listOf(Screen.Chat, Screen.Contacts, Screen.Pairing, Screen.Identity)
                        screens.forEach { screen ->
                            NavigationBarItem(
                                selected = activeScreen.route == screen.route,
                                onClick = { activeScreen = screen },
                                icon = { Icon(screen.icon, contentDescription = screen.title) },
                                label = { Text(screen.title) },
                                colors = NavigationBarItemDefaults.colors(
                                    selectedIconColor = MaterialTheme.colorScheme.primary,
                                    selectedTextColor = MaterialTheme.colorScheme.primary,
                                    indicatorColor = InputSurface,
                                    unselectedIconColor = MutedText,
                                    unselectedTextColor = MutedText
                                )
                            )
                        }
                    }
                }
            ) { innerPadding ->
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding)
                        .background(MaterialTheme.colorScheme.background)
                ) {
                    when (activeScreen) {
                        Screen.Chat -> ChatComposeScreen()
                        Screen.Contacts -> ContactsComposeScreen()
                        Screen.Pairing -> PairingComposeScreen()
                        Screen.Identity -> IdentityComposeScreen(onLock = { isUnlocked = false })
                    }
                }
            }
        }
    }
}
