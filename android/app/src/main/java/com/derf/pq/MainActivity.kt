package com.derf.pq

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccessibilityNew
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.Group
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class MainActivity : ComponentActivity() {

    companion object {
        @JvmStatic
        var singletonThis: MainActivity? = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        singletonThis = this

        // Request Android Runtime Permissions (Notifications & Storage)
        requestAndroidPermissions()

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

    private fun requestAndroidPermissions() {
        val permissionsToRequest = mutableListOf<String>()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                permissionsToRequest.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            permissionsToRequest.add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            permissionsToRequest.add(Manifest.permission.RECORD_AUDIO)
        }

        if (permissionsToRequest.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, permissionsToRequest.toTypedArray(), 101)
        }
    }
}

fun isAccessibilityServiceEnabled(context: Context, serviceClass: Class<*>): Boolean {
    val expectedComponentName = "${context.packageName}/${serviceClass.canonicalName}"
    val enabledServices = Settings.Secure.getString(
        context.contentResolver,
        Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
    ) ?: return false

    val colonSplitter = TextUtils.SimpleStringSplitter(':')
    colonSplitter.setString(enabledServices)

    while (colonSplitter.hasNext()) {
        val componentName = colonSplitter.next()
        if (componentName.equals(expectedComponentName, ignoreCase = true)) {
            return true
        }
    }
    return false
}

sealed class Screen(val route: String, val title: String, val icon: androidx.compose.ui.graphics.vector.ImageVector) {
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

    val context = LocalContext.current
    var showPermissionBanner by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        // Check if Derf Accessibility Quick Peek service is enabled
        val isEnabled = isAccessibilityServiceEnabled(context, DerfAccessibilityService::class.java)
        showPermissionBanner = !isEnabled
    }

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
                    Column {
                        TopAppBar(
                            title = {
                                Text(
                                    text = "DERF PQ MESSENGER",
                                    color = MaterialTheme.colorScheme.primary,
                                    style = MaterialTheme.typography.titleMedium
                                )
                            },
                            actions = {
                                IconButton(onClick = {
                                    val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                                    intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                                    context.startActivity(intent)
                                }) {
                                    Icon(
                                        imageVector = Icons.Default.AccessibilityNew,
                                        contentDescription = "Enable Quick-Peek Accessibility Service",
                                        tint = ElectricCyan
                                    )
                                }
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

                        if (showPermissionBanner) {
                            Surface(
                                color = CardSurface,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 12.dp, vertical = 4.dp),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(8.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = " Enable Quick-Peek Accessibility Overlay for in-place decryption",
                                        color = ElectricCyan,
                                        fontSize = 12.sp,
                                        modifier = Modifier.weight(1f)
                                    )
                                    Button(
                                        onClick = {
                                            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                                            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                                            context.startActivity(intent)
                                        },
                                        colors = ButtonDefaults.buttonColors(containerColor = ElectricCyan, contentColor = ObsidianBackground),
                                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                                        shape = RoundedCornerShape(6.dp)
                                    ) {
                                        Text("ENABLE", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                    }
                                }
                            }
                        }
                    }
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
