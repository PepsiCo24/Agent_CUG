package com.agentcug;

import com.agentcug.model.entity.User;
import com.agentcug.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableAsync
public class AgentCugApplication {
    private static final Logger log = LoggerFactory.getLogger(AgentCugApplication.class);

    public static void main(String[] args) {
        SpringApplication.run(AgentCugApplication.class, args);
    }

    @Bean
    CommandLineRunner bootstrapAdmin(UserRepository userRepository,
                                     PasswordEncoder passwordEncoder,
                                     @Value("${app.bootstrap-admin.username:admin}") String username,
                                     @Value("${app.bootstrap-admin.password:}") String password) {
        return args -> {
            if (userRepository.existsByUsername(username)) {
                return;
            }

            if (password == null || password.length() < 8) {
                log.warn("Initial admin was not created: APP_BOOTSTRAP_ADMIN_PASSWORD must be at least 8 characters.");
                return;
            }

            userRepository.save(User.builder()
                    .username(username)
                    .password(passwordEncoder.encode(password))
                    .email(username + "@localhost")
                    .nickname("管理员")
                    .build());
            log.info("Initial admin account '{}' created.", username);
        };
    }
}
