package com.glothriel.dgmobile;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        TextView greeting = new TextView(this);
        greeting.setText(R.string.greeting);
        greeting.setTextSize(28);
        greeting.setGravity(Gravity.CENTER);
        setContentView(greeting);
    }
}
