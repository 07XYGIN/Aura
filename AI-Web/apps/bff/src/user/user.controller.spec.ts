import { Test, TestingModule } from '@nestjs/testing'
import { UserController } from './user.controller'
import { UserService } from './user.service'

describe('UserController', () => {
    let controller: UserController

    beforeEach(async () => {
        const module: TestingModule = await Test.createTestingModule({
            controllers: [UserController],
            providers: [
                {
                    provide: UserService,
                    useValue: {
                        register: jest.fn(),
                        login: jest.fn(),
                        logout: jest.fn(),
                        getUserInfo: jest.fn(),
                        updateInfo: jest.fn(),
                        deleteUser: jest.fn(),
                    },
                },
            ],
        }).compile()

        controller = module.get<UserController>(UserController)
    })

    it('should be defined', () => {
        expect(controller).toBeDefined()
    })
})
